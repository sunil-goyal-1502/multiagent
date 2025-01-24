from typing import Dict, Optional
import logging
from pathlib import Path
import yaml
import jinja2
from datetime import datetime

from .config import Config

logger = logging.getLogger(__name__)

class TemplateManager:
    def __init__(self, config: Optional[Config] = None):
        self.config = config
        self.templates = {}
        self.environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.load_templates()

    def load_templates(self) -> None:
        """Load all templates from the templates directory."""
        try:
            templates_dir = Path("templates")
            
            # Load agent-specific templates
            for agent_dir in templates_dir.glob("*"):
                if agent_dir.is_dir():
                    agent_name = agent_dir.name
                    self.templates[agent_name] = {}
                    
                    # Load YAML templates
                    for yaml_file in agent_dir.glob("*.yml"):
                        with open(yaml_file) as f:
                            templates = yaml.safe_load(f)
                            self.templates[agent_name].update(templates)
                    
                    # Load Jinja templates
                    for template_file in agent_dir.glob("*.j2"):
                        template_name = template_file.stem
                        self.templates[agent_name][template_name] = \
                            self.environment.get_template(
                                f"{agent_name}/{template_file.name}"
                            )
            
            logger.info("Successfully loaded templates")
            
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            raise

    def get_template(
        self,
        template_name: str,
        agent: Optional[str] = None
    ) -> str:
        """Get template by name and optionally agent."""
        if agent and agent in self.templates:
            if template_name in self.templates[agent]:
                return self.templates[agent][template_name]
        
        # Try finding template in common templates
        if "common" in self.templates and template_name in self.templates["common"]:
            return self.templates["common"][template_name]
            
        raise KeyError(f"Template not found: {template_name}")

    def render_template(
        self,
        template_name: str,
        context: Dict,
        agent: Optional[str] = None
    ) -> str:
        """Render template with context."""
        template = self.get_template(template_name, agent)
        
        # Add common context variables
        full_context = {
            "now": datetime.now(),
            "config": self.config.to_dict() if self.config else {},
            **context
        }
        
        try:
            if isinstance(template, str):
                # Handle YAML templates
                return template.format(**full_context)
            else:
                # Handle Jinja templates
                return template.render(**full_context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def create_prompt(
        self,
        template_name: str,
        context: Dict,
        agent: Optional[str] = None
    ) -> str:
        """Create an LLM prompt from template."""
        template = self.get_template(template_name, agent)
        
        # Add system context for LLM
        prompt_context = {
            "system_prompt": self._get_system_prompt(agent),
            **context
        }
        
        return self.render_template(template_name, prompt_context, agent)

    def _get_system_prompt(self, agent: Optional[str] = None) -> str:
        """Get system prompt for agent."""
        if agent and agent in self.templates:
            return self.templates[agent].get(
                "system_prompt",
                self.templates["common"]["system_prompt"]
            )
        return self.templates["common"]["system_prompt"]

    def create_content_structure(
        self,
        content_type: str,
        context: Dict
    ) -> Dict:
        """Create content structure from template."""
        structure_template = self.get_template(f"{content_type}_structure")
        
        if isinstance(structure_template, str):
            # Parse YAML template
            structure = yaml.safe_load(structure_template)
        else:
            # Render Jinja template
            rendered = structure_template.render(**context)
            structure = yaml.safe_load(rendered)
            
        return structure

    def validate_template(
        self,
        template_name: str,
        agent: Optional[str] = None
    ) -> bool:
        """Validate template syntax."""
        try:
            template = self.get_template(template_name, agent)
            
            if isinstance(template, str):
                # Validate string template
                template.format(**{
                    key: "test" for key in self._extract_format_keys(template)
                })
            else:
                # Validate Jinja template
                template.render(
                    **{
                        key: "test" for key in template.variable_names
                    }
                )
            return True
            
        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            return False

    def _extract_format_keys(self, template: str) -> set:
        """Extract format keys from string template."""
        import re
        return set(re.findall(r'\{(\w+)\}', template))

    def reload_templates(self) -> None:
        """Reload all templates."""
        self.templates = {}
        self.load_templates()

    def add_template(
        self,
        template_name: str,
        template_content: str,
        agent: Optional[str] = None
    ) -> None:
        """Add a new template."""
        if agent:
            if agent not in self.templates:
                self.templates[agent] = {}
            self.templates[agent][template_name] = template_content
        else:
            if "common" not in self.templates:
                self.templates["common"] = {}
            self.templates["common"][template_name] = template_content

    def remove_template(
        self,
        template_name: str,
        agent: Optional[str] = None
    ) -> bool:
        """Remove a template."""
        try:
            if agent:
                del self.templates[agent][template_name]
            else:
                del self.templates["common"][template_name]
            return True
        except KeyError:
            return False
