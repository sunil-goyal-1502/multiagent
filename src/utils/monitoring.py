from typing import Dict, List, Optional
import logging
from datetime import datetime
import json
from pathlib import Path
import asyncio

from .config import Config

logger = logging.getLogger(__name__)

class PipelineMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.events = {}
        self.metrics = {}
        self.alerts = []
        self.logs_dir = Path(config.get("monitoring.logs_path", "./logs"))
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    async def track_pipeline(self, pipeline_id: str) -> None:
        """Track pipeline execution."""
        self.events[pipeline_id] = []
        self.metrics[pipeline_id] = {
            "start_time": datetime.now().isoformat(),
            "agent_metrics": {},
            "resource_usage": [],
            "completion_time": None
        }
        
        # Start resource monitoring
        asyncio.create_task(self._monitor_resources(pipeline_id))

    async def log_event(
        self,
        pipeline_id: str,
        event_type: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Log a pipeline event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "description": description,
            "metadata": metadata or {}
        }
        
        self.events[pipeline_id].append(event)
        
        # Check for alerts
        await self._check_alerts(pipeline_id, event)
        
        # Log to file
        await self._write_to_log(pipeline_id, event)

    async def record_metric(
        self,
        pipeline_id: str,
        agent: str,
        metric_name: str,
        value: float
    ) -> None:
        """Record a performance metric."""
        if agent not in self.metrics[pipeline_id]["agent_metrics"]:
            self.metrics[pipeline_id]["agent_metrics"][agent] = {}
            
        metrics = self.metrics[pipeline_id]["agent_metrics"][agent]
        
        if metric_name not in metrics:
            metrics[metric_name] = []
            
        metrics[metric_name].append({
            "timestamp": datetime.now().isoformat(),
            "value": value
        })

    async def _monitor_resources(self, pipeline_id: str) -> None:
        """Monitor system resource usage."""
        import psutil
        
        while pipeline_id in self.metrics:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                
                self.metrics[pipeline_id]["resource_usage"].append({
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_info.percent,
                    "memory_used": memory_info.used,
                    "memory_available": memory_info.available
                })
                
                # Check resource thresholds
                await self._check_resource_thresholds(pipeline_id, cpu_percent, memory_info)
                
                await asyncio.sleep(
                    self.config.get("monitoring.resource_check_interval", 60)
                )
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                break

    async def _check_resource_thresholds(
        self,
        pipeline_id: str,
        cpu_percent: float,
        memory_info: Any
    ) -> None:
        """Check if resource usage exceeds thresholds."""
        thresholds = self.config.get("monitoring.thresholds", {})
        
        if cpu_percent > thresholds.get("cpu_percent", 90):
            await self._create_alert(
                pipeline_id,
                "HIGH_CPU_USAGE",
                f"CPU usage at {cpu_percent}%"
            )
            
        if memory_info.percent > thresholds.get("memory_percent", 90):
            await self._create_alert(
                pipeline_id,
                "HIGH_MEMORY_USAGE",
                f"Memory usage at {memory_info.percent}%"
            )

    async def _check_alerts(self, pipeline_id: str, event: Dict) -> None:
        """Check if event should trigger alerts."""
        if event["type"] == "error":
            await self._create_alert(
                pipeline_id,
                "PIPELINE_ERROR",
                event["description"],
                event["metadata"]
            )
            
        # Check for timing alerts
        if event["type"] == "agent_complete":
            agent = event["metadata"].get("agent")
            duration = event["metadata"].get("duration")
            
            if duration:
                threshold = self.config.get(
                    f"monitoring.thresholds.{agent}_duration",
                    300  # 5 minutes default
                )
                
                if duration > threshold:
                    await self._create_alert(
                        pipeline_id,
                        "SLOW_AGENT",
                        f"{agent} took {duration} seconds to complete",
                        {"agent": agent, "duration": duration}
                    )

    async def _create_alert(
        self,
        pipeline_id: str,
        alert_type: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Create and handle an alert."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "pipeline_id": pipeline_id,
            "type": alert_type,
            "message": message,
            "metadata": metadata or {},
            "status": "new"
        }
        
        self.alerts.append(alert)
        
        # Log alert
        logger.warning(f"Alert: {alert_type} - {message}")
        
        # Handle alert based on type
        await self._handle_alert(alert)

    async def _handle_alert(self, alert: Dict) -> None:
        """Handle different types of alerts."""
        handlers = {
            "PIPELINE_ERROR": self._handle_pipeline_error,
            "HIGH_CPU_USAGE": self._handle_resource_alert,
            "HIGH_MEMORY_USAGE": self._handle_resource_alert,
            "SLOW_AGENT": self._handle_performance_alert
        }
        
        handler = handlers.get(alert["type"])
        if handler:
            await handler(alert)

    async def _handle_pipeline_error(self, alert: Dict) -> None:
        """Handle pipeline error alerts."""
        # Log detailed error information
        error_log = Path(self.logs_dir) / "errors.log"
        async with aiofiles.open(error_log, 'a') as f:
            await f.write(f"{json.dumps(event, indent=2)}\n")

    async def _send_notification(self, alert: Dict) -> None:
        """Send notification for alert."""
        notification_config = self.config.get("monitoring.notifications", {})
        
        if notification_config.get("email.enabled"):
            await self._send_email_notification(alert)
            
        if notification_config.get("slack.enabled"):
            await self._send_slack_notification(alert)

    async def _send_email_notification(self, alert: Dict) -> None:
        """Send email notification."""
        email_config = self.config.get("monitoring.notifications.email", {})
        # Implement email sending logic here

    async def _send_slack_notification(self, alert: Dict) -> None:
        """Send Slack notification."""
        slack_config = self.config.get("monitoring.notifications.slack", {})
        # Implement Slack notification logic here

    async def _manage_cpu_usage(self, alert: Dict) -> None:
        """Manage high CPU usage."""
        # Implement CPU management strategies
        pass

    async def _manage_memory_usage(self, alert: Dict) -> None:
        """Manage high memory usage."""
        # Implement memory management strategies
        pass

    async def get_pipeline_metrics(self, pipeline_id: str) -> Dict:
        """Get comprehensive metrics for a pipeline."""
        if pipeline_id not in self.metrics:
            return {}
            
        pipeline_metrics = self.metrics[pipeline_id]
        events = self.events.get(pipeline_id, [])
        
        return {
            "duration": self._calculate_duration(pipeline_metrics),
            "agent_performance": self._calculate_agent_performance(pipeline_metrics),
            "resource_usage": self._calculate_resource_usage(pipeline_metrics),
            "event_summary": self._summarize_events(events),
            "alerts": self._get_pipeline_alerts(pipeline_id)
        }

    def _calculate_duration(self, metrics: Dict) -> Optional[float]:
        """Calculate total pipeline duration."""
        if not metrics.get("completion_time"):
            return None
            
        start_time = datetime.fromisoformat(metrics["start_time"])
        end_time = datetime.fromisoformat(metrics["completion_time"])
        return (end_time - start_time).total_seconds()

    def _calculate_agent_performance(self, metrics: Dict) -> Dict:
        """Calculate performance metrics for each agent."""
        performance = {}
        
        for agent, agent_metrics in metrics["agent_metrics"].items():
            performance[agent] = {
                "average_duration": self._calculate_average(
                    agent_metrics.get("duration", [])
                ),
                "success_rate": self._calculate_success_rate(
                    agent_metrics.get("success", [])
                ),
                "error_rate": self._calculate_error_rate(
                    agent_metrics.get("errors", [])
                )
            }
            
        return performance

    def _calculate_resource_usage(self, metrics: Dict) -> Dict:
        """Calculate resource usage statistics."""
        resource_data = metrics.get("resource_usage", [])
        
        if not resource_data:
            return {}
            
        return {
            "cpu": {
                "average": self._calculate_average(
                    [r["cpu_percent"] for r in resource_data]
                ),
                "peak": max(r["cpu_percent"] for r in resource_data)
            },
            "memory": {
                "average": self._calculate_average(
                    [r["memory_percent"] for r in resource_data]
                ),
                "peak": max(r["memory_percent"] for r in resource_data)
            }
        }

    def _summarize_events(self, events: List[Dict]) -> Dict:
        """Create summary of pipeline events."""
        event_types = {}
        errors = []
        
        for event in events:
            event_type = event["type"]
            event_types[event_type] = event_types.get(event_type, 0) + 1
            
            if event_type == "error":
                errors.append({
                    "timestamp": event["timestamp"],
                    "description": event["description"]
                })
                
        return {
            "total_events": len(events),
            "event_distribution": event_types,
            "error_count": len(errors),
            "errors": errors[:5]  # Return only last 5 errors
        }

    def _get_pipeline_alerts(self, pipeline_id: str) -> List[Dict]:
        """Get alerts for specific pipeline."""
        return [
            alert for alert in self.alerts 
            if alert["pipeline_id"] == pipeline_id
        ]

    def _calculate_average(self, values: List[float]) -> float:
        """Calculate average of values."""
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _calculate_success_rate(self, successes: List[bool]) -> float:
        """Calculate success rate."""
        if not successes:
            return 0.0
        return sum(1 for s in successes if s) / len(successes)

    def _calculate_error_rate(self, errors: List[Dict]) -> float:
        """Calculate error rate."""
        if not errors:
            return 0.0
        total_operations = len(errors)
        error_count = sum(1 for e in errors if e["severity"] in ["high", "critical"])
        return error_count / total_operations

    async def get_events(self, pipeline_id: str) -> List[Dict]:
        """Get all events for a pipeline."""
        return self.events.get(pipeline_id, [])

    async def get_metrics(self, pipeline_id: str) -> Dict:
        """Get raw metrics for a pipeline."""
        return self.metrics.get(pipeline_id, {})

    async def get_alerts(
        self,
        pipeline_id: Optional[str] = None,
        alert_type: Optional[str] = None
    ) -> List[Dict]:
        """Get alerts with optional filtering."""
        filtered_alerts = self.alerts
        
        if pipeline_id:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert["pipeline_id"] == pipeline_id
            ]
            
        if alert_type:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert["type"] == alert_type
            ]
            
        return filtered_alerts

    async def mark_pipeline_complete(self, pipeline_id: str) -> None:
        """Mark pipeline as complete and calculate final metrics."""
        if pipeline_id in self.metrics:
            self.metrics[pipeline_id]["completion_time"] = datetime.now().isoformat()
            
            # Calculate final metrics
            final_metrics = await self.get_pipeline_metrics(pipeline_id)
            
            # Log completion
            await self.log_event(
                pipeline_id,
                "pipeline_complete",
                "Pipeline execution completed",
                final_metrics
            )

    async def cleanup(self) -> None:
        """Cleanup monitoring resources."""
        # Save metrics and events to disk if configured
        if self.config.get("monitoring.save_history", True):
            history_dir = self.logs_dir / "history"
            history_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save metrics
            metrics_file = history_dir / f"metrics_{timestamp}.json"
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
                
            # Save events
            events_file = history_dir / f"events_{timestamp}.json"
            with open(events_file, 'w') as f:
                json.dump(self.events, f, indent=2)
                
            # Save alerts
            alerts_file = history_dir / f"alerts_{timestamp}.json"
            with open(alerts_file, 'w') as f:
                json.dump(self.alerts, f, indent=2)
                
        # Clear memory
        self.events = {}
        self.metrics = {}
        self.alerts = []dumps(alert, indent=2)}\n")
            
        # Notify if configured
        if self.config.get("monitoring.notifications.enabled"):
            await self._send_notification(alert)

    async def _handle_resource_alert(self, alert: Dict) -> None:
        """Handle resource-related alerts."""
        # Implement resource management strategies
        if alert["type"] == "HIGH_CPU_USAGE":
            await self._manage_cpu_usage(alert)
        elif alert["type"] == "HIGH_MEMORY_USAGE":
            await self._manage_memory_usage(alert)

    async def _handle_performance_alert(self, alert: Dict) -> None:
        """Handle performance-related alerts."""
        # Log performance issue
        performance_log = Path(self.logs_dir) / "performance.log"
        async with aiofiles.open(performance_log, 'a') as f:
            await f.write(f"{json.dumps(alert, indent=2)}\n")

    async def _write_to_log(self, pipeline_id: str, event: Dict) -> None:
        """Write event to log file."""
        log_file = self.logs_dir / f"{pipeline_id}.log"
        async with aiofiles.open(log_file, 'a') as f:
            await f.write(f"{json.
