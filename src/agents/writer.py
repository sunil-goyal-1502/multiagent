from typing import Dict, List, Optional
import logging
from datetime import datetime

from .base import BaseAgent, AgentRole, Message
from src.utils.content import ContentGenerator, StyleGuide
from src.utils.templates import TemplateManager
from src.utils.config import Config

logger = logging.getLogger(__name__)

class WriterAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.WRITER, config)
        self.content_generator = ContentGenerator(config)
        self.style_guide = StyleGuide(config)
        self.template_manager = TemplateManager()
        self.writing_history = []

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process writing tasks."""
        if "research_data" not in message.content:
            return self._create_error_message(
                message,
                "No research data provided"
            )

        try:
            article = await self.write_article(
                message.content["research_data"],
                message.content["topic"]
            )
            
            return Message(
                sender=self.role,
                receiver=AgentRole.EDITOR,
                content={
                    "draft_article": article,
                    "research_data": message.content["research_data"],
                    "metadata": self._create_metadata(message)
                }
            )
        except Exception as e:
            logger.error(f"Writing error: {e}")
            return self._create_error_message(message, str(e))

    async def write_article(self, research_data: Dict, topic: str) -> Dict:
        """Generate article from research data."""
        # Create outline
        outline = await self._create_outline(research_data, topic)
        
        # Generate content for each section
        sections = []
        for section in outline:
            content = await self._write_section(
                section,
                research_data,
                outline
            )
            sections.append(content)

        # Assemble the article
        article = await self._assemble_article(sections, research_data, topic)
        
        # Apply style guide
        article = self.style_guide.apply(article)
        
        # Store in writing history
        self.writing_history.append({
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "outline": outline,
            "article_id": article["id"]
        })

        return article

    async def _create_outline(self, research_data: Dict, topic: str) -> List[Dict]:
        """Create article outline from research data."""
        # Analyze key points
        main_points = research_data["main_points"]
        trends = research_data["trends"]
        
        # Generate outline using LLM
        outline_prompt = self.template_manager.get_template("outline")
        outline_prompt = outline_prompt.format(
            topic=topic,
            main_points=main_points,
            trends=trends
        )
        
        outline_response = await self.llm.generate(outline_prompt)
        outline = self.content_generator.parse_outline(outline_response)
        
        return outline

    async def _write_section(
        self,
        section: Dict,
        research_data: Dict,
        outline: List[Dict]
    ) -> Dict:
        """Write a single section of the article."""
        # Get relevant research data for section
        section_data = self._get_section_data(section, research_data)
        
        # Generate section content
        section_prompt = self.template_manager.get_template("section")
        section_prompt = section_prompt.format(
            section_title=section["title"],
            section_type=section["type"],
            key_points=section_data["key_points"],
            statistics=section_data["statistics"],
            style_guide=self.style_guide.get_rules()
        )
        
        content = await self.llm.generate(section_prompt)
        
        return {
            "title": section["title"],
            "content": content,
            "type": section["type"],
            "sources": section_data["sources"]
        }

    def _get_section_data(self, section: Dict, research_data: Dict) -> Dict:
        """Get relevant research data for a section."""
        section_data = {
            "key_points": [],
            "statistics": [],
            "sources": []
        }
        
        # Filter relevant key points
        for point in research_data["main_points"]:
            if self._is_relevant_to_section(point, section):
                section_data["key_points"].append(point)
        
        # Filter relevant statistics
        for stat in research_data["statistics"]:
            if self._is_relevant_to_section(stat, section):
                section_data["statistics"].append(stat)
        
        # Add sources
        section_data["sources"] = [
            source for source in research_data["sources"]
            if self._is_relevant_to_section(source, section)
        ]
        
        return section_data

    def _is_relevant_to_section(self, item: Dict, section: Dict) -> bool:
        """Check if a research item is relevant to a section."""
        # Compare keywords and categories
        item_keywords = set(item.get("keywords", []))
        section_keywords = set(section.get("keywords", []))
        
        # Check direct category match
        if item.get("category") == section.get("category"):
            return True
            
        # Check keyword overlap
        keyword_overlap = len(item_keywords & section_keywords)
        return keyword_overlap > 0

    async def _assemble_article(
        self,
        sections: List[Dict],
        research_data: Dict,
        topic: str
    ) -> Dict:
        """Assemble final article from sections."""
        # Generate title and introduction
        title = await self._generate_title(topic, research_data)
        introduction = await self._write_introduction(topic, research_data)
        
        # Generate conclusion
        conclusion = await self._write_conclusion(sections, research_data)
        
        # Assemble metadata
        metadata = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "research_timestamp": research_data["metadata"]["timestamp"],
            "word_count": sum(len(s["content"].split()) for s in sections),
            "sources": research_data["sources"]
        }
        
        return {
            "id": self._generate_article_id(topic),
            "title": title,
            "introduction": introduction,
            "sections": sections,
            "conclusion": conclusion,
            "metadata": metadata
        }

    async def _generate_title(self, topic: str, research_data: Dict) -> str:
        """Generate engaging article title."""
        title_prompt = self.template_manager.get_template("title")
        title_prompt = title_prompt.format(
            topic=topic,
            main_points=research_data["main_points"][:3],
            style_guide=self.style_guide.get_rules()
        )
        
        title = await self.llm.generate(title_prompt)
        return title.strip()

    def _create_metadata(self, message: Message) -> Dict:
        """Create metadata for the article."""
        return {
            "original_topic": message.content["topic"],
            "research_timestamp": message.content["research_data"]["metadata"]["timestamp"],
            "writing_timestamp": datetime.now().isoformat(),
            "agent_version": self.config.get("writer.version", "1.0.0")
        }

    def _generate_article_id(self, topic: str) -> str:
        """Generate unique article ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_slug = topic.lower().replace(" ", "_")
        return f"article_{topic_slug}_{timestamp}"
