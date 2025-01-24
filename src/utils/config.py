from typing import Any, Dict, Optional
import yaml
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_data: Dict):
        self._config = config_data
        self._validate_config()

    @classmethod
    def load_from_file(cls, file_path: str) -> 'Config':
        """Load configuration from YAML file."""
        try:
            with open(file_path, 'r') as f:
                config_data = yaml.safe_load(f)
            return cls(config_data)
        except Exception as e:
            logger.error(f"Failed to load config from {file_path}: {e}")
            raise

    @classmethod
    def load_from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        config_data = {
            "llm": {
                "model": os.getenv("LLM_MODEL", "gpt-4"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            },
            "agents": {
                "researcher": {
                    "search_apis": os.getenv("SEARCH_APIS", "google,scopus").split(","),
                    "max_sources": int(os.getenv("MAX_SOURCES", "10"))
                },
                "writer": {
                    "style_guide": os.getenv("STYLE_GUIDE", "default"),
                    "tone": os.getenv("CONTENT_TONE", "professional")
                },
                # Add other agent configs
            }
        }
        return cls(config_data)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        try:
            value = self._config
            for part in key.split('.'):
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation."""
        parts = key.split('.')
        config = self._config
        
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
            
        config[parts[-1]] = value

    def _validate_config(self) -> None:
        """Validate configuration structure and required fields."""
        required_sections = [
            "llm",
            "agents.researcher",
            "agents.writer",
            "agents.editor",
            "agents.seo",
            "agents.image",
            "agents.publisher"
        ]
        
        for section in required_sections:
            if not self.get(section):
                raise ValueError(f"Missing required config section: {section}")

        self._validate_api_keys()
        self._validate_agent_configs()

    def _validate_api_keys(self) -> None:
        """Validate required API keys are present."""
        required_keys = [
            ("llm.api_key", "OpenAI API key"),
            ("agents.researcher.search_apis", "Search API configuration")
        ]
        
        for key, description in required_keys:
            if not self.get(key):
                raise ValueError(f"Missing required {description}")

    def _validate_agent_configs(self) -> None:
        """Validate agent-specific configurations."""
        agent_validations = {
            "researcher": self._validate_researcher_config,
            "writer": self._validate_writer_config,
            "editor": self._validate_editor_config,
            "seo": self._validate_seo_config,
            "image": self._validate_image_config,
            "publisher": self._validate_publisher_config
        }
        
        for agent, validation_func in agent_validations.items():
            validation_func()

    def _validate_researcher_config(self) -> None:
        """Validate researcher agent configuration."""
        researcher_config = self.get("agents.researcher", {})
        required_fields = ["search_apis", "max_sources"]
        
        for field in required_fields:
            if field not in researcher_config:
                raise ValueError(f"Missing required researcher config: {field}")

    def _validate_writer_config(self) -> None:
        """Validate writer agent configuration."""
        writer_config = self.get("agents.writer", {})
        required_fields = ["style_guide", "tone"]
        
        for field in required_fields:
            if field not in writer_config:
                raise ValueError(f"Missing required writer config: {field}")

    def _validate_editor_config(self) -> None:
        """Validate editor agent configuration."""
        editor_config = self.get("agents.editor", {})
        required_fields = ["grammar_checker", "style_guide"]
        
        for field in required_fields:
            if field not in editor_config:
                raise ValueError(f"Missing required editor config: {field}")

    def _validate_seo_config(self) -> None:
        """Validate SEO agent configuration."""
        seo_config = self.get("agents.seo", {})
        required_fields = ["tools"]
        
        for field in required_fields:
            if field not in seo_config:
                raise ValueError(f"Missing required SEO config: {field}")

    def _validate_image_config(self) -> None:
        """Validate image agent configuration."""
        image_config = self.get("agents.image", {})
        required_fields = ["generator", "style"]
        
        for field in required_fields:
            if field not in image_config:
                raise ValueError(f"Missing required image config: {field}")

    def _validate_publisher_config(self) -> None:
        """Validate publisher agent configuration."""
        publisher_config = self.get("agents.publisher", {})
        required_fields = ["platforms"]
        
        for field in required_fields:
            if field not in publisher_config:
                raise ValueError(f"Missing required publisher config: {field}")

    def save(self, file_path: Optional[str] = None) -> None:
        """Save current configuration to file."""
        if not file_path:
            file_path = 'config.yml'
            
        try:
            with open(file_path, 'w') as f:
                yaml.safe_dump(self._config, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save config to {file_path}: {e}")
            raise

    def merge(self, other_config: 'Config') -> None:
        """Merge another config into this one."""
        self._merge_dict(self._config, other_config._config)
        self._validate_config()

    def _merge_dict(self, dict1: Dict, dict2: Dict) -> None:
        """Recursively merge dictionaries."""
        for key, value in dict2.items():
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
                self._merge_dict(dict1[key], value)
            else:
                dict1[key] = value

    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return self._config.copy()
