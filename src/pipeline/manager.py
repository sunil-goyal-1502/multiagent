from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime

from ..agents import (
    AgentRole,
    Message,
    ResearchAgent,
    WriterAgent,
    EditorAgent,
    SEOAgent,
    ImageAgent,
    PublisherAgent
)
from ..utils.config import Config
from ..utils.monitoring import PipelineMonitor

logger = logging.getLogger(__name__)

class ContentPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.monitor = PipelineMonitor(config)
        
        # Initialize agents
        self.agents = {
            AgentRole.RESEARCHER: ResearchAgent(config),
            AgentRole.WRITER: WriterAgent(config),
            AgentRole.EDITOR: EditorAgent(config),
            AgentRole.SEO: SEOAgent(config),
            AgentRole.IMAGE: ImageAgent(config),
            AgentRole.PUBLISHER: PublisherAgent(config)
        }
        
        # Set up agent registry
        for agent in self.agents.values():
            agent.agent_registry = self.agents
        
        self.workflow = self.create_workflow()
        self.pipeline_status = {}

    def create_workflow(self) -> Dict:
        """Create the agent workflow configuration."""
        return {
            AgentRole.RESEARCHER: [AgentRole.WRITER],
            AgentRole.WRITER: [AgentRole.EDITOR],
            AgentRole.EDITOR: [AgentRole.SEO],
            AgentRole.SEO: [AgentRole.IMAGE],
            AgentRole.IMAGE: [AgentRole.PUBLISHER],
            AgentRole.PUBLISHER: []
        }

    async def start_pipeline(
        self,
        topic: str,
        style_guide: Optional[str] = None,
        target_length: Optional[int] = None
    ):
        """Start the content creation pipeline."""
        pipeline_id = self._generate_pipeline_id(topic)
        
        try:
            # Initialize pipeline monitoring
            self.pipeline_status[pipeline_id] = {
                "status": "started",
                "start_time": datetime.now().isoformat(),
                "current_stage": AgentRole.RESEARCHER,
                "completed_stages": [],
                "errors": []
            }
            
            # Start monitoring
            asyncio.create_task(self.monitor.track_pipeline(pipeline_id))

            # Create initial message
            initial_message = Message(
                sender=None,
                receiver=AgentRole.RESEARCHER,
                content={
                    "research_topic": topic,
                    "style_guide": style_guide,
                    "target_length": target_length,
                    "pipeline_id": pipeline_id
                }
            )

            # Start all agents
            agent_tasks = []
            for agent in self.agents.values():
                agent_tasks.append(asyncio.create_task(agent.run()))

            # Start the pipeline
            await self.agents[AgentRole.RESEARCHER].message_queue.put(initial_message)

            # Monitor pipeline progress
            await self.monitor_pipeline(pipeline_id)

            return pipeline_id

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.pipeline_status[pipeline_id]["status"] = "failed"
            self.pipeline_status[pipeline_id]["errors"].append(str(e))
            raise

    async def monitor_pipeline(self, pipeline_id: str):
        """Monitor pipeline progress."""
        while True:
            status = self.pipeline_status[pipeline_id]
            
            if status["status"] in ["completed", "failed"]:
                break
                
            # Check if publisher has completed
            if status["current_stage"] == AgentRole.PUBLISHER and \
               AgentRole.PUBLISHER in status["completed_stages"]:
                status["status"] = "completed"
                status["end_time"] = datetime.now().isoformat()
                break
                
            await asyncio.sleep(1)

    async def get_pipeline_status(self, pipeline_id: str) -> Dict:
        """Get current pipeline status."""
        status = self.pipeline_status.get(pipeline_id, {})
        if not status:
            return {"error": "Pipeline not found"}
            
        # Add performance metrics
        metrics = await self.monitor.get_metrics(pipeline_id)
        
        return {
            **status,
            "metrics": metrics,
            "stage_durations": await self._calculate_stage_durations(pipeline_id)
        }

    async def _calculate_stage_durations(self, pipeline_id: str) -> Dict:
        """Calculate duration of each completed stage."""
        events = await self.monitor.get_events(pipeline_id)
        durations = {}
        
        for stage in AgentRole:
            stage_events = [e for e in events if e["stage"] == stage]
            if len(stage_events) >= 2:  # Has start and end events
                start = datetime.fromisoformat(stage_events[0]["timestamp"])
                end = datetime.fromisoformat(stage_events[-1]["timestamp"])
                durations[stage.value] = (end - start).total_seconds()
                
        return durations

    def _generate_pipeline_id(self, topic: str) -> str:
        """Generate unique pipeline ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_slug = topic.lower().replace(" ", "_")
        return f"pipeline_{topic_slug}_{timestamp}"

    async def shutdown(self):
        """Shutdown all agents and cleanup."""
        shutdown_tasks = []
        for agent in self.agents.values():
            shutdown_tasks.append(agent.shutdown())
        
        await asyncio.gather(*shutdown_tasks)
        await self.monitor.shutdown()

# Usage Example
async def main():
    config = Config.load_from_file("config.yml")
    pipeline = ContentPipeline(config)
    
    try:
        pipeline_id = await pipeline.start_pipeline(
            topic="AI in Healthcare",
            style_guide="technical",
            target_length=2000
        )
        
        # Monitor progress
        while True:
            status = await pipeline.get_pipeline_status(pipeline_id)
            if status["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(5)
            
        print(f"Pipeline completed: {status}")
        
    finally:
        await pipeline.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
