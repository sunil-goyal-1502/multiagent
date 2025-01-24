from typing import Dict, List, Optional
import logging
from datetime import datetime

from .base import BaseAgent, AgentRole, Message
from ..utils.seo import KeywordAnalyzer, SEOOptimizer, MetadataGenerator
from ..utils.config import Config

logger = logging.getLogger(__name__)

class SEOAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.SEO, config)
        self.keyword_analyzer = KeywordAnalyzer(config)
        self.seo_optimizer = SEOOptimizer(config)
        self.metadata_generator = MetadataGenerator()

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process SEO optimization tasks."""
        if "edited_article" not in message.content:
            return self._create_error_message(
                message,
                "No edited article provided"
            )

        try:
            optimized_article = await self.optimize_article(
                message.content["edited_article"]
            )
            
            return Message(
                sender=self.role,
                receiver=AgentRole.IMAGE,
                content={
                    "seo_optimized_article": optimized_article,
                    "original_research": message.content.get("original_research", {})
                }
            )
        except Exception as e:
            logger.error(f"SEO optimization error: {e}")
            return self._create_error_message(message, str(e))

    async def optimize_article(self, article: Dict) -> Dict:
        """Optimize article for search engines."""
        # Analyze keywords and topics
        keywords = await self.keyword_analyzer.analyze_content(article)
        
        # Optimize content
        optimized = await self._optimize_content(article, keywords)
        
        # Generate SEO metadata
        seo_metadata = await self.metadata_generator.generate(
            optimized,
            keywords
        )
        
        return {
            **optimized,
            "seo_metadata": seo_metadata,
            "keywords": keywords
        }

    async def _optimize_content(self, article: Dict, keywords: Dict) -> Dict:
        """Apply SEO optimizations to article content."""
        optimized = article.copy()
        
        # Optimize title
        optimized["title"] = await self.seo_optimizer.optimize_title(
            article["title"],
            keywords["primary"]
        )
        
        # Optimize meta description
        optimized["meta_description"] = await self.seo_optimizer.create_meta_description(
            article["introduction"],
            keywords["primary"]
        )
        
        # Optimize headings
        optimized["sections"] = await self._optimize_sections(
            article["sections"],
            keywords
        )
        
        # Optimize content
        optimized = await self._optimize_main_content(optimized, keywords)
        
        return optimized

    async def _optimize_sections(
        self,
        sections: List[Dict],
        keywords: Dict
    ) -> List[Dict]:
        """Optimize section headings and content."""
        optimized_sections = []
        
        for section in sections:
            optimized_section = section.copy()
            
            # Optimize section title
            optimized_section["title"] = await self.seo_optimizer.optimize_heading(
                section["title"],
                keywords["secondary"]
            )
            
            # Optimize section content
            optimized_section["content"] = await self.seo_optimizer.optimize_content(
                section["content"],
                keywords["primary"],
                keywords["secondary"]
            )
            
            optimized_sections.append(optimized_section)
        
        return optimized_sections

    async def _optimize_main_content(self, article: Dict, keywords: Dict) -> Dict:
        """Optimize main content for keyword density and readability."""
        optimized = article.copy()
        
        # Optimize URL slug
        optimized["url_slug"] = self.seo_optimizer.generate_slug(
            article["title"],
            keywords["primary"]
        )
        
        # Add schema markup
        optimized["schema_markup"] = await self.metadata_generator.generate_schema(
            article,
            keywords
        )
        
        # Optimize internal linking
        optimized = await self.seo_optimizer.optimize_internal_linking(optimized)
        
        # Add structured data
        optimized["structured_data"] = self.metadata_generator.generate_structured_data(
            optimized
        )
        
        return optimized

    def _create_seo_report(self, article: Dict, keywords: Dict) -> Dict:
        """Create SEO optimization report."""
        return {
            "primary_keyword": keywords["primary"],
            "secondary_keywords": keywords["secondary"],
            "keyword_density": self._calculate_keyword_density(article, keywords),
            "meta_description_length": len(article.get("meta_description", "")),
            "title_length": len(article["title"]),
            "url_slug": article.get("url_slug", ""),
            "readability_score": self._calculate_readability(article),
            "heading_structure": self._analyze_heading_structure(article),
            "internal_links": len(article.get("internal_links", [])),
            "has_schema_markup": "schema_markup" in article,
            "optimization_timestamp": datetime.now().isoformat()
        }

    def _calculate_keyword_density(self, article: Dict, keywords: Dict) -> Dict:
        """Calculate keyword density in the content."""
        text = f"{article['title']} {article['introduction']} "
        text += " ".join(section["content"] for section in article["sections"])
        text += f" {article['conclusion']}"
        
        word_count = len(text.split())
        densities = {}
        
        # Calculate for primary keyword
        primary_count = text.lower().count(keywords["primary"].lower())
        densities["primary"] = (primary_count / word_count) * 100
        
        # Calculate for secondary keywords
        densities["secondary"] = {}
        for keyword in keywords["secondary"]:
            count = text.lower().count(keyword.lower())
            densities["secondary"][keyword] = (count / word_count) * 100
            
        return densities

    def _calculate_readability(self, article: Dict) -> float:
        """Calculate content readability score."""
        return self.seo_optimizer.calculate_readability_score(article)

    def _analyze_heading_structure(self, article: Dict) -> Dict:
        """Analyze heading structure for SEO."""
        headings = {
            "h1": [article["title"]],
            "h2": [section["title"] for section in article["sections"]],
            "h3": []  # Add if you have subsections
        }
        
        return {
            "structure": headings,
            "has_primary_keyword_in_h1": self._check_keyword_in_heading(
                headings["h1"][0],
                article.get("keywords", {}).get("primary", "")
            )
        }

    def _check_keyword_in_heading(self, heading: str, keyword: str) -> bool:
        """Check if keyword is present in heading."""
        return keyword.lower() in heading.lower()
