from typing import Dict, List, Optional
import logging
from datetime import datetime
import asyncio

from .base import BaseAgent, AgentRole, Message
from src.utils.image import ImageGenerator, ImageOptimizer, ImageAnalyzer
from src.utils.config import Config

logger = logging.getLogger(__name__)

class ImageAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.IMAGE, config)
        self.image_generator = ImageGenerator(config)
        self.image_optimizer = ImageOptimizer()
        self.image_analyzer = ImageAnalyzer()
        self.generation_history = []

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process image generation tasks."""
        if "seo_optimized_article" not in message.content:
            return self._create_error_message(
                message,
                "No optimized article provided"
            )

        try:
            article_with_images = await self.generate_images(
                message.content["seo_optimized_article"]
            )
            
            return Message(
                sender=self.role,
                receiver=AgentRole.PUBLISHER,
                content={
                    "article_with_images": article_with_images,
                    "image_metadata": self._create_image_metadata()
                }
            )
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return self._create_error_message(message, str(e))

    async def generate_images(self, article: Dict) -> Dict:
        """Generate and optimize images for article."""
        enhanced_article = article.copy()
        
        # Generate featured image
        featured_image = await self._generate_featured_image(article)
        enhanced_article["featured_image"] = featured_image
        
        # Generate section images
        enhanced_article["sections"] = await self._generate_section_images(
            article["sections"]
        )
        
        # Generate social media images
        social_images = await self._generate_social_images(article)
        enhanced_article["social_images"] = social_images
        
        # Store generation history
        self.generation_history.append({
            "article_id": article["id"],
            "timestamp": datetime.now().isoformat(),
            "generated_images": {
                "featured": featured_image["id"],
                "sections": [img["id"] for section in enhanced_article["sections"]
                           for img in section.get("images", [])],
                "social": [img["id"] for img in social_images]
            }
        })
        
        return enhanced_article

    async def _generate_featured_image(self, article: Dict) -> Dict:
        """Generate featured image for article."""
        prompt = await self._create_image_prompt(
            article["title"],
            article.get("keywords", {}).get("primary", ""),
            "featured"
        )
        
        image = await self.image_generator.generate(
            prompt,
            size="large",
            style=self.config.get("image.style", "modern")
        )
        
        # Optimize image
        optimized = await self.image_optimizer.optimize(
            image,
            target_formats=["jpg", "webp"]
        )
        
        # Add metadata
        image_data = {
            "id": self._generate_image_id("featured"),
            "original": image,
            "optimized": optimized,
            "alt_text": await self._generate_alt_text(article["title"]),
            "caption": await self._generate_caption(article["title"]),
            "metadata": {
                "prompt": prompt,
                "style": self.config.get("image.style", "modern"),
                "generated_at": datetime.now().isoformat()
            }
        }
        
        return image_data

    async def _generate_section_images(self, sections: List[Dict]) -> List[Dict]:
        """Generate images for each section where appropriate."""
        enhanced_sections = []
        
        for section in sections:
            enhanced_section = section.copy()
            
            # Determine if section needs an image
            if await self._should_add_section_image(section):
                prompt = await self._create_image_prompt(
                    section["title"],
                    section.get("keywords", []),
                    "section"
                )
                
                image = await self.image_generator.generate(
                    prompt,
                    size="medium",
                    style=self.config.get("image.style", "modern")
                )
                
                # Optimize image
                optimized = await self.image_optimizer.optimize(
                    image,
                    target_formats=["jpg", "webp"]
                )
                
                enhanced_section["images"] = [{
                    "id": self._generate_image_id("section"),
                    "original": image,
                    "optimized": optimized,
                    "alt_text": await self._generate_alt_text(section["title"]),
                    "caption": await self._generate_caption(section["title"]),
                    "metadata": {
                        "prompt": prompt,
                        "style": self.config.get("image.style", "modern"),
                        "generated_at": datetime.now().isoformat()
                    }
                }]
            
            enhanced_sections.append(enhanced_section)
        
        return enhanced_sections

    async def _generate_social_images(self, article: Dict) -> List[Dict]:
        """Generate images optimized for social media platforms."""
        social_image_specs = {
            "twitter": {"width": 1200, "height": 630},
            "facebook": {"width": 1200, "height": 630},
            "linkedin": {"width": 1104, "height": 736}
        }
        
        social_images = []
        
        for platform, specs in social_image_specs.items():
            prompt = await self._create_image_prompt(
                article["title"],
                article.get("keywords", {}).get("primary", ""),
                f"social_{platform}"
            )
            
            image = await self.image_generator.generate(
                prompt,
                size=specs,
                style=self.config.get("image.style", "modern")
            )
            
            optimized = await self.image_optimizer.optimize(
                image,
                target_formats=["jpg", "webp"]
            )
            
            social_images.append({
                "id": self._generate_image_id(f"social_{platform}"),
                "platform": platform,
                "original": image,
                "optimized": optimized,
                "metadata": {
                    "prompt": prompt,
                    "specs": specs,
                    "generated_at": datetime.now().isoformat()
                }
            })
        
        return social_images

    async def _create_image_prompt(
        self,
        text: str,
        keywords: str,
        image_type: str
    ) -> str:
        """Create optimized prompt for image generation."""
        prompt_template = self.config.get(f"image.prompts.{image_type}")
        if not prompt_template:
            prompt_template = self.config.get("image.prompts.default")
        
        # Analyze text for visual elements
        visual_elements = await self.image_analyzer.extract_visual_elements(text)
        
        # Combine elements into prompt
        prompt = prompt_template.format(
            text=text,
            keywords=keywords,
            style=self.config.get("image.style", "modern"),
            visual_elements=", ".join(visual_elements)
        )
        
        return prompt

    async def _should_add_section_image(self, section: Dict) -> bool:
        """Determine if a section should include an image."""
        # Check content length
        if len(section["content"].split()) < 200:
            return False
        
        # Check if content is visual-friendly
        visual_score = await self.image_analyzer.calculate_visual_score(
            section["content"]
        )
        
        # Check section type
        if section.get("type") in ["code", "table", "list"]:
            return False
            
        return visual_score > 0.6

    async def _generate_alt_text(self, context: str) -> str:
        """Generate SEO-friendly alt text for images."""
        prompt = f"Generate descriptive alt text for an image about: {context}"
        alt_text = await self.llm.generate(prompt)
        return alt_text.strip()

    async def _generate_caption(self, context: str) -> str:
        """Generate engaging caption for images."""
        prompt = f"Generate an engaging image caption for: {context}"
        caption = await self.llm.generate(prompt)
        return caption.strip()

    def _generate_image_id(self, prefix: str) -> str:
        """Generate unique image ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"img_{prefix}_{timestamp}"

    def _create_image_metadata(self) -> Dict:
        """Create metadata about image generation process."""
        return {
            "generator_version": self.config.get("image.version", "1.0.0"),
            "style_used": self.config.get("image.style", "modern"),
            "timestamp": datetime.now().isoformat(),
            "generated_formats": ["jpg", "webp"],
            "optimization_settings": self.image_optimizer.get_settings()
        }
