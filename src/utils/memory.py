from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import json
from collections import deque
import asyncio
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

class AgentMemory:
    def __init__(self, agent_role: str, config: Config):
        self.agent_role = agent_role
        self.config = config
        self.short_term = deque(maxlen=config.get("memory.short_term_size", 100))
        self.long_term = {}
        self.patterns = {}
        self.memory_file = Path(config.get(
            "memory.storage_path",
            "./data/memory"
        )) / f"{agent_role}_memory.json"
        
        self.load_memory()

    async def store_interaction(self, message: Any) -> None:
        """Store an interaction in memory."""
        interaction = self._format_interaction(message)
        
        # Store in short-term memory
        self.short_term.append(interaction)
        
        # Update patterns
        await self._update_patterns(interaction)
        
        # Potentially move to long-term memory
        await self._consider_long_term_storage(interaction)

    def _format_interaction(self, message: Any) -> Dict:
        """Format message for storage."""
        return {
            "timestamp": datetime.now().isoformat(),
            "content": message.to_dict() if hasattr(message, "to_dict") else message,
            "type": type(message).__name__
        }

    async def _update_patterns(self, interaction: Dict) -> None:
        """Update observed patterns in interactions."""
        # Extract patterns from interaction
        new_patterns = await self._extract_patterns(interaction)
        
        # Update pattern frequencies
        for pattern in new_patterns:
            pattern_id = self._generate_pattern_id(pattern)
            if pattern_id not in self.patterns:
                self.patterns[pattern_id] = {
                    "pattern": pattern,
                    "count": 0,
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat()
                }
            
            self.patterns[pattern_id]["count"] += 1
            self.patterns[pattern_id]["last_seen"] = datetime.now().isoformat()
        
        # Cleanup old patterns
        await self._cleanup_patterns()

    async def _extract_patterns(self, interaction: Dict) -> List[Dict]:
        """Extract patterns from an interaction."""
        patterns = []
        
        # Time-based patterns
        time_pattern = self._extract_time_pattern(interaction)
        if time_pattern:
            patterns.append(time_pattern)
        
        # Content-based patterns
        content_patterns = await self._extract_content_patterns(interaction)
        patterns.extend(content_patterns)
        
        # Sequence patterns
        sequence_patterns = self._extract_sequence_patterns()
        patterns.extend(sequence_patterns)
        
        return patterns

    def _extract_time_pattern(self, interaction: Dict) -> Optional[Dict]:
        """Extract time-based patterns."""
        timestamp = datetime.fromisoformat(interaction["timestamp"])
        
        return {
            "type": "time",
            "hour": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "interaction_type": interaction["type"]
        }

    async def _extract_content_patterns(self, interaction: Dict) -> List[Dict]:
        """Extract patterns from interaction content."""
        patterns = []
        content = interaction["content"]
        
        if isinstance(content, dict):
            # Check for repeated fields
            for key, value in content.items():
                if self._is_frequent_value(key, value):
                    patterns.append({
                        "type": "content",
                        "field": key,
                        "value": value
                    })
        
        return patterns

    def _extract_sequence_patterns(self) -> List[Dict]:
        """Extract patterns from interaction sequences."""
        if len(self.short_term) < 2:
            return []
            
        patterns = []
        recent_interactions = list(self.short_term)[-5:]  # Look at last 5 interactions
        
        # Look for repeated sequences
        for i in range(len(recent_interactions) - 1):
            current = recent_interactions[i]
            next_interaction = recent_interactions[i + 1]
            
            pattern = {
                "type": "sequence",
                "first": current["type"],
                "second": next_interaction["type"]
            }
            
            patterns.append(pattern)
        
        return patterns

    def _is_frequent_value(self, key: str, value: Any) -> bool:
        """Check if a value appears frequently for a given key."""
        threshold = self.config.get("memory.frequency_threshold", 3)
        count = 0
        
        for interaction in self.short_term:
            if isinstance(interaction["content"], dict):
                if interaction["content"].get(key) == value:
                    count += 1
                    
        return count >= threshold

    async def _consider_long_term_storage(self, interaction: Dict) -> None:
        """Consider moving interaction to long-term memory."""
        # Check if interaction matches any significant patterns
        significant_patterns = self._find_significant_patterns(interaction)
        
        if significant_patterns:
            # Store in long-term memory
            memory_key = self._generate_memory_key(interaction)
            self.long_term[memory_key] = {
                "interaction": interaction,
                "patterns": significant_patterns,
                "stored_at": datetime.now().isoformat()
            }
            
            # Save to disk if configured
            if self.config.get("memory.persistent", True):
                await self.save_memory()

    def _find_significant_patterns(self, interaction: Dict) -> List[Dict]:
        """Find significant patterns related to an interaction."""
        significant_patterns = []
        pattern_threshold = self.config.get("memory.pattern_threshold", 5)
        
        for pattern in self.patterns.values():
            if pattern["count"] >= pattern_threshold:
                if self._interaction_matches_pattern(interaction, pattern["pattern"]):
                    significant_patterns.append(pattern)
                    
        return significant_patterns

    def _interaction_matches_pattern(self, interaction: Dict, pattern: Dict) -> bool:
        """Check if interaction matches a pattern."""
        if pattern["type"] == "time":
            timestamp = datetime.fromisoformat(interaction["timestamp"])
            return (
                timestamp.hour == pattern["hour"] and
                timestamp.weekday() == pattern["day_of_week"] and
                interaction["type"] == pattern["interaction_type"]
            )
        elif pattern["type"] == "content":
            content = interaction["content"]
            return (
                isinstance(content, dict) and
                content.get(pattern["field"]) == pattern["value"]
            )
        elif pattern["type"] == "sequence":
            # Check if this interaction could be part of the sequence
            return interaction["type"] in [pattern["first"], pattern["second"]]
        
        return False

    def _generate_pattern_id(self, pattern: Dict) -> str:
        """Generate unique ID for a pattern."""
        return f"{pattern['type']}_{hash(str(sorted(pattern.items())))}"

    def _generate_memory_key(self, interaction: Dict) -> str:
        """Generate unique key for long-term memory storage."""
        timestamp = interaction["timestamp"].replace(":", "_")
        return f"{timestamp}_{hash(str(interaction))}"

    async def _cleanup_patterns(self) -> None:
        """Clean up old or irrelevant patterns."""
        now = datetime.now()
        cleanup_threshold = self.config.get("memory.cleanup_threshold_days", 30)
        
        patterns_to_remove = []
        for pattern_id, pattern in self.patterns.items():
            last_seen = datetime.fromisoformat(pattern["last_seen"])
            days_since_last_seen = (now - last_seen).days
            
            if days_since_last_seen > cleanup_threshold:
                patterns_to_remove.append(pattern_id)
        
        for pattern_id in patterns_to_remove:
            del self.patterns[pattern_id]

    async def recall(
        self,
        criteria: Optional[Dict] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Recall interactions from memory based on criteria."""
        matches = []
        
        # Search in short-term memory
        for interaction in reversed(self.short_term):
            if self._matches_criteria(interaction, criteria):
                matches.append(interaction)
        
        # Search in long-term memory
        for memory in self.long_term.values():
            if self._matches_criteria(memory["interaction"], criteria):
                matches.append(memory["interaction"])
        
        # Sort by timestamp
        matches.sort(key=lambda x: x["timestamp"], reverse=True)
        
        if limit:
            matches = matches[:limit]
            
        return matches

    def _matches_criteria(self, interaction: Dict, criteria: Optional[Dict]) -> bool:
        """Check if interaction matches search criteria."""
        if not criteria:
            return True
            
        for key, value in criteria.items():
            if key == "time_range":
                timestamp = datetime.fromisoformat(interaction["timestamp"])
                if not (value["start"] <= timestamp <= value["end"]):
                    return False
            elif key == "type":
                if interaction["type"] != value:
                    return False
            elif key == "content":
                if not self._content_matches(interaction["content"], value):
                    return False
                    
        return True

    def _content_matches(self, content: Any, criteria: Dict) -> bool:
        """Check if content matches criteria."""
        if isinstance(content, dict) and isinstance(criteria, dict):
            for key, value in criteria.items():
                if key not in content or content[key] != value:
                    return False
            return True
        return False

    async def summarize(self) -> Dict:
        """Generate a summary of memory contents."""
        return {
            "short_term_size": len(self.short_term),
            "long_term_size": len(self.long_term),
            "patterns_discovered": len(self.patterns),
            "most_common_patterns": self._get_most_common_patterns(5),
            "memory_stats": self._calculate_memory_stats()
        }

    def _get_most_common_patterns(self, limit: int) -> List[Dict]:
        """Get most frequently observed patterns."""
        sorted_patterns = sorted(
            self.patterns.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        return sorted_patterns[:limit]

    def _calculate_memory_stats(self) -> Dict:
        """Calculate memory usage statistics."""
        return {
            "total_interactions": len(self.short_term) + len(self.long_term),
            "pattern_distribution": self._get_pattern_distribution(),
            "temporal_distribution": self._get_temporal_distribution(),
            "type_distribution": self._get_type_distribution()
        }

    def _get_pattern_distribution(self) -> Dict:
        """Get distribution of pattern types."""
        distribution = {}
        for pattern in self.patterns.values():
            pattern_type = pattern["pattern"]["type"]
            distribution[pattern_type] = distribution.get(pattern_type, 0) + 1
        return distribution

    def _get_temporal_distribution(self) -> Dict:
        """Get temporal distribution of interactions."""
        distribution = {
            "hourly": [0] * 24,
            "daily": [0] * 7
        }
        
        for interaction in self.short_term:
            timestamp = datetime.fromisoformat(interaction["timestamp"])
            distribution["hourly"][timestamp.hour] += 1
            distribution["daily"][timestamp.weekday()] += 1
            
        return distribution

    def _get_type_distribution(self) -> Dict:
        """Get distribution of interaction types."""
        distribution = {}
        for interaction in self.short_term:
            interaction_type = interaction["type"]
            distribution[interaction_type] = distribution.get(interaction_type, 0) + 1
        return distribution

    def load_memory(self) -> None:
        """Load memory from disk."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.long_term = data.get("long_term", {})
                    self.patterns = data.get("patterns", {})
                    
                logger.info(f"Loaded memory for agent {self.agent_role}")
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")

    async def save_memory(self) -> None:
        """Save memory to disk."""
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.memory_file, 'w') as f:
                json.dump({
                    "long_term": self.long_term,
                    "patterns": self.patterns
                }, f, indent=2)
                
            logger.info(f"Saved memory for agent {self.agent_role}")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    async def cleanup(self) -> None:
        """Cleanup and save memory before shutdown."""
        await self._cleanup_patterns()
        if self.config.get("memory.persistent", True):
            await self.save_memory()
