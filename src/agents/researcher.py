from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime

from .base import BaseAgent, AgentRole, Message
from src.utils.research import SearchAPI, ContentAnalyzer, SourceValidator
from src.utils.config import Config

logger = logging.getLogger(__name__)

class ResearchAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.RESEARCHER, config)
        self.search_api = SearchAPI(config)
        self.content_analyzer = ContentAnalyzer()
        self.source_validator = SourceValidator(config)
        self.research_cache = {}

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process research tasks."""
        if "research_topic" not in message.content:
            return self._create_error_message(
                message,
                "No research topic provided"
            )

        topic = message.content["research_topic"]
        try:
            research_data = await self.gather_research(topic)
            return Message(
                sender=self.role,
                receiver=AgentRole.WRITER,
                content={
                    "research_data": research_data,
                    "topic": topic
                }
            )
        except Exception as e:
            logger.error(f"Research error: {e}")
            return self._create_error_message(message, str(e))

    async def gather_research(self, topic: str) -> Dict:
        """Gather comprehensive research on a topic."""
        # Check cache first
        cache_key = self._generate_cache_key(topic)
        if cache_key in self.research_cache:
            if self._is_cache_valid(self.research_cache[cache_key]):
                return self.research_cache[cache_key]["data"]

        # Perform research tasks in parallel
        tasks = [
            self.extract_key_points(topic),
            self.find_reliable_sources(topic),
            self.gather_statistics(topic),
            self.analyze_trends(topic)
        ]
        
        results = await asyncio.gather(*tasks)
        
        research_data = {
            "main_points": results[0],
            "sources": results[1],
            "statistics": results[2],
            "trends": results[3],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "topic": topic
            }
        }

        # Cache the results
        self.research_cache[cache_key] = {
            "data": research_data,
            "timestamp": datetime.now()
        }

        return research_data

    async def extract_key_points(self, topic: str) -> List[Dict]:
        """Extract key points about the topic."""
        search_results = await self.search_api.search(
            topic,
            max_results=self.config.get("researcher.max_sources", 10)
        )
        
        key_points = []
        for result in search_results:
            if await self.source_validator.is_reliable(result["url"]):
                content = await self.search_api.fetch_content(result["url"])
                points = await self.content_analyzer.extract_key_points(content)
                key_points.extend(points)
        
        return self._deduplicate_points(key_points)

    async def find_reliable_sources(self, topic: str) -> List[Dict]:
        """Find reliable sources about the topic."""
        sources = await self.search_api.search_academic(
            topic,
            max_results=self.config.get("researcher.max_academic_sources", 5)
        )
        
        reliable_sources = []
        for source in sources:
            if await self.source_validator.is_reliable(source["url"]):
                reliable_sources.append({
                    "url": source["url"],
                    "title": source["title"],
                    "author": source.get("author"),
                    "published_date": source.get("published_date"),
                    "citation_count": source.get("citation_count")
                })
        
        return reliable_sources

    async def gather_statistics(self, topic: str) -> List[Dict]:
        """Gather relevant statistics about the topic."""
        stats = await self.search_api.search_statistics(topic)
        validated_stats = []
        
        for stat in stats:
            if await self.source_validator.verify_statistic(stat):
                validated_stats.append({
                    "value": stat["value"],
                    "metric": stat["metric"],
                    "source": stat["source"],
                    "year": stat["year"],
                    "confidence": stat["confidence"]
                })
        
        return validated_stats

    async def analyze_trends(self, topic: str) -> Dict:
        """Analyze trends related to the topic."""
        trends = await self.search_api.search_trends(topic)
        return {
            "historical_data": trends["historical"],
            "current_trends": trends["current"],
            "future_predictions": trends["predictions"],
            "related_topics": trends["related"],
            "sentiment_analysis": await self._analyze_sentiment(topic)
        }

    async def _analyze_sentiment(self, topic: str) -> Dict:
        """Analyze sentiment around the topic."""
        recent_content = await self.search_api.search_recent(topic, days=30)
        sentiments = []
        
        for content in recent_content:
            sentiment = await self.content_analyzer.analyze_sentiment(content)
            sentiments.append(sentiment)
        
        return {
            "overall": sum(s["score"] for s in sentiments) / len(sentiments),
            "distribution": {
                "positive": len([s for s in sentiments if s["score"] > 0.5]),
                "neutral": len([s for s in sentiments if 0.3 <= s["score"] <= 0.7]),
                "negative": len([s for s in sentiments if s["score"] < 0.3])
            },
            "key_phrases": await self._extract_sentiment_phrases(sentiments)
        }

    async def _extract_sentiment_phrases(self, sentiments: List[Dict]) -> Dict:
        """Extract key phrases by sentiment category."""
        return {
            "positive": [s["key_phrases"] for s in sentiments if s["score"] > 0.7],
            "negative": [s["key_phrases"] for s in sentiments if s["score"] < 0.3]
        }

    def _generate_cache_key(self, topic: str) -> str:
        """Generate cache key for a topic."""
        return f"{topic.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid."""
        cache_age = datetime.now() - datetime.fromisoformat(cache_entry["timestamp"])
        max_age = self.config.get("researcher.cache_ttl_hours", 24)
        return cache_age.total_seconds() < (max_age * 3600)

    def _deduplicate_points(self, points: List[Dict]) -> List[Dict]:
        """Remove duplicate key points."""
        seen = set()
        unique_points = []
        
        for point in points:
            point_hash = self._hash_point(point)
            if point_hash not in seen:
                seen.add(point_hash)
                unique_points.append(point)
        
        return unique_points

    def _hash_point(self, point: Dict) -> str:
        """Create a hash for a key point for deduplication."""
        return f"{point['category']}_{point['content'][:100]}"
