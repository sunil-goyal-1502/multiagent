from typing import Dict, List, Optional
import logging
from datetime import datetime

from .base import BaseAgent, AgentRole, Message
from src.utils.publisher import ContentPublisher, QualityChecker, AssetManager
from src.utils.config import Config

logger = logging.getLogger(__name__)

class PublisherAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.PUBLISHER, config)
        self.content_publisher = ContentPublisher(config)
        self.quality_checker = QualityChecker()
        self.asset_manager = AssetManager(config)
        self.publish_history = []

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process publishing tasks."""
        if "article_with_images" not in message.content:
            return self._create_error_message(
                message,
                "No article provided for publishing"
            )

        try:
            publish_result = await self.publish_content(
                message.content["article_with_images"]
            )
            
            # Create final status message
            return Message(
                sender=self.role,
                receiver=None,  # Final stage
                content={
                    "publish_result": publish_result,
                    "publish_metadata": self._create_publish_metadata(message)
                }
            )
        except Exception as e:
            logger.error(f"Publishing error: {e}")
            return self._create_error_message(message, str(e))

    async def publish_content(self, article: Dict) -> Dict:
        """Publish content across specified platforms."""
        # Final quality check
        quality_report = await self.quality_checker.check_content(article)
        if not self._is_quality_acceptable(quality_report):
            raise ValueError(f"Content quality check failed: {quality_report}")

        # Prepare assets
        assets = await self.asset_manager.prepare_assets(article)
        
        # Publish to configured platforms
        publish_results = {}
        platforms = self.config.get("publisher.platforms", ["default"])
        
        for platform in platforms:
            try:
                result = await self.content_publisher.publish(
                    content=article,
                    assets=assets,
                    platform=platform
                )
                publish_results[platform] = result
            except Exception as e:
                logger.error(f"Publishing failed for {platform}: {e}")
                publish_results[platform] = {
                    "status": "failed",
                    "error": str(e)
                }

        # Store publish history
        self.publish_history.append({
            "article_id": article["id"],
            "timestamp": datetime.now().isoformat(),
            "platforms": platforms,
            "results": publish_results
        })

        return {
            "status": "completed",
            "platforms": publish_results,
            "urls": self._extract_published_urls(publish_results)
        }

    async def _pre_publish_check(self, article: Dict) -> Dict:
        """Perform final checks before publishing."""
        checks = {
            "content": await self._check_content(article),
            "images": await self._check_images(article),
            "seo": await self._check_seo(article),
            "compliance": await self._check_compliance(article)
        }
        
        return {
            "passed": all(check["passed"] for check in checks.values()),
            "checks": checks
        }

    async def _check_content(self, article: Dict) -> Dict:
        """Check content quality and completeness."""
        issues = []
        
        # Check required fields
        required_fields = ["title", "introduction", "sections", "conclusion"]
        for field in required_fields:
            if field not in article:
                issues.append(f"Missing required field: {field}")

        # Check content length
        min_length = self.config.get("publisher.min_word_count", 1000)
        word_count = len(" ".join([
            article["title"],
            article["introduction"],
            *[s["content"] for s in article["sections"]],
            article["conclusion"]
        ]).split())
        
        if word_count < min_length:
            issues.append(f"Content length below minimum: {word_count}/{min_length}")

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

    async def _check_images(self, article: Dict) -> Dict:
        """Check image assets."""
        issues = []
        
        # Check featured image
        if "featured_image" not in article:
            issues.append("Missing featured image")
        
        # Check image optimizations
        image_specs = self.config.get("publisher.image_specs", {})
        for platform, specs in image_specs.items():
            if not self.asset_manager.verify_image_specs(
                article.get("social_images", []),
                platform,
                specs
            ):
                issues.append(f"Missing or invalid image for {platform}")

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

    async def _check_seo(self, article: Dict) -> Dict:
        """Check SEO requirements."""
        issues = []
        
        seo_requirements = [
            ("meta_description", "Missing meta description"),
            ("keywords", "Missing keywords"),
            ("url_slug", "Missing URL slug")
        ]
        
        for field, message in seo_requirements:
            if field not in article:
                issues.append(message)

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

    async def _check_compliance(self, article: Dict) -> Dict:
        """Check content compliance."""
        compliance_report = await self.quality_checker.check_compliance(article)
        
        return {
            "passed": compliance_report["passed"],
            "issues": compliance_report.get("issues", [])
        }

    def _is_quality_acceptable(self, quality_report: Dict) -> bool:
        """Determine if quality is acceptable for publishing."""
        min_score = self.config.get("publisher.min_quality_score", 0.8)
        return quality_report["overall_score"] >= min_score

    def _extract_published_urls(self, publish_results: Dict) -> Dict:
        """Extract published URLs from results."""
        urls = {}
        for platform, result in publish_results.items():
            if result.get("status") == "success":
                urls[platform] = result.get("url")
        return urls

    def _create_publish_metadata(self, message: Message) -> Dict:
        """Create metadata about publishing process."""
        return {
            "publisher_version": self.config.get("publisher.version", "1.0.0"),
            "timestamp": datetime.now().isoformat(),
            "platforms": self.config.get("publisher.platforms", ["default"]),
            "original_article_id": message.content["article_with_images"]["id"]
        }
