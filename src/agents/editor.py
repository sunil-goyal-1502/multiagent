from typing import Dict, List, Optional
import logging
from datetime import datetime

from .base import BaseAgent, AgentRole, Message
from ..utils.grammar import GrammarChecker
from ..utils.style import StyleChecker
from ..utils.content import ContentAnalyzer
from ..utils.config import Config

logger = logging.getLogger(__name__)

class EditorAgent(BaseAgent):
    def __init__(self, config: Config):
        super().__init__(AgentRole.EDITOR, config)
        self.grammar_checker = GrammarChecker(config)
        self.style_checker = StyleChecker(config)
        self.content_analyzer = ContentAnalyzer()
        self.edit_history = []

    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process editing tasks."""
        if "draft_article" not in message.content:
            return self._create_error_message(
                message,
                "No draft article provided"
            )

        try:
            edited_article = await self.edit_article(
                message.content["draft_article"],
                message.content.get("research_data", {})
            )
            
            return Message(
                sender=self.role,
                receiver=AgentRole.SEO,
                content={
                    "edited_article": edited_article,
                    "original_research": message.content.get("research_data", {}),
                    "editing_metadata": self._create_editing_metadata(message)
                }
            )
        except Exception as e:
            logger.error(f"Editing error: {e}")
            return self._create_error_message(message, str(e))

    async def edit_article(self, article: Dict, research_data: Dict) -> Dict:
        """Edit and improve the article."""
        # Create working copy
        edited_article = article.copy()
        
        # Perform various checks
        grammar_issues = await self._check_grammar(edited_article)
        style_issues = await self._check_style(edited_article)
        content_issues = await self._analyze_content(edited_article, research_data)
        
        # Apply fixes
        edited_article = await self._fix_grammar(edited_article, grammar_issues)
        edited_article = await self._fix_style(edited_article, style_issues)
        edited_article = await self._improve_content(edited_article, content_issues)
        
        # Verify improvements
        quality_score = await self._assess_quality(edited_article)
        
        # Store edit history
        self.edit_history.append({
            "article_id": article["id"],
            "timestamp": datetime.now().isoformat(),
            "improvements": {
                "grammar": len(grammar_issues),
                "style": len(style_issues),
                "content": len(content_issues)
            },
            "quality_score": quality_score
        })

        return {
            **edited_article,
            "quality_score": quality_score,
            "edit_metadata": {
                "grammar_improvements": len(grammar_issues),
                "style_improvements": len(style_issues),
                "content_improvements": len(content_issues),
                "timestamp": datetime.now().isoformat()
            }
        }

    async def _check_grammar(self, article: Dict) -> List[Dict]:
        """Check for grammar issues."""
        issues = []
        
        # Check title
        title_issues = await self.grammar_checker.check_text(article["title"])
        issues.extend(self._format_issues("title", title_issues))
        
        # Check introduction
        intro_issues = await self.grammar_checker.check_text(article["introduction"])
        issues.extend(self._format_issues("introduction", intro_issues))
        
        # Check each section
        for i, section in enumerate(article["sections"]):
            section_issues = await self.grammar_checker.check_text(section["content"])
            issues.extend(self._format_issues(f"section_{i}", section_issues))
        
        # Check conclusion
        conclusion_issues = await self.grammar_checker.check_text(article["conclusion"])
        issues.extend(self._format_issues("conclusion", conclusion_issues))
        
        return issues

    async def _check_style(self, article: Dict) -> List[Dict]:
        """Check for style issues."""
        style_issues = []
        
        # Check overall style consistency
        style_rules = self.style_checker.get_rules()
        
        # Check title style
        title_issues = await self.style_checker.check_text(
            article["title"],
            style_rules["title"]
        )
        style_issues.extend(self._format_issues("title", title_issues))
        
        # Check content style
        for i, section in enumerate(article["sections"]):
            section_issues = await self.style_checker.check_text(
                section["content"],
                style_rules["content"]
            )
            style_issues.extend(self._format_issues(f"section_{i}", section_issues))
        
        # Check tone consistency
        tone_issues = await self.style_checker.check_tone_consistency(article)
        style_issues.extend(tone_issues)
        
        return style_issues

    async def _analyze_content(self, article: Dict, research_data: Dict) -> List[Dict]:
        """Analyze content quality and accuracy."""
        content_issues = []
        
        # Check factual accuracy
        accuracy_issues = await self._check_factual_accuracy(article, research_data)
        content_issues.extend(accuracy_issues)
        
        # Check content flow
        flow_issues = await self._check_content_flow(article)
        content_issues.extend(flow_issues)
        
        # Check for missing key points
        missing_points = await self._check_coverage(article, research_data)
        content_issues.extend(missing_points)
        
        return content_issues

    async def _check_factual_accuracy(self, article: Dict, research_data: Dict) -> List[Dict]:
        """Check if article facts match research data."""
        issues = []
        
        # Extract facts from article
        article_facts = await self.content_analyzer.extract_facts(article)
        
        # Compare with research data
        for fact in article_facts:
            if not self._verify_fact(fact, research_data):
                issues.append({
                    "type": "factual_accuracy",
                    "severity": "high",
                    "description": f"Unverified fact: {fact['text']}",
                    "location": fact["location"],
                    "suggestion": "Verify fact against research data or remove"
                })
        
        return issues

    def _verify_fact(self, fact: Dict, research_data: Dict) -> bool:
        """Verify a fact against research data."""
        # Check main points
        for point in research_data.get("main_points", []):
            if self._facts_match(fact, point):
                return True
        
        # Check statistics
        for stat in research_data.get("statistics", []):
            if self._facts_match(fact, stat):
                return True
        
        return False

    def _facts_match(self, fact1: Dict, fact2: Dict) -> bool:
        """Check if two facts match in meaning."""
        # Compare numerical values if present
        if "value" in fact1 and "value" in fact2:
            return abs(fact1["value"] - fact2["value"]) < 0.01
        
        # Compare textual content
        return self.content_analyzer.calculate_similarity(
            fact1["text"],
            fact2["text"]
        ) > 0.8

    async def _fix_grammar(self, article: Dict, issues: List[Dict]) -> Dict:
        """Fix grammar issues in the article."""
        edited_article = article.copy()
        
        for issue in sorted(issues, key=lambda x: x["severity"], reverse=True):
            if issue["location"] == "title":
                edited_article["title"] = await self._apply_grammar_fix(
                    edited_article["title"],
                    issue
                )
            elif issue["location"].startswith("section_"):
                section_idx = int(issue["location"].split("_")[1])
                edited_article["sections"][section_idx]["content"] = \
                    await self._apply_grammar_fix(
                        edited_article["sections"][section_idx]["content"],
                        issue
                    )
            elif issue["location"] == "conclusion":
                edited_article["conclusion"] = await self._apply_grammar_fix(
                    edited_article["conclusion"],
                    issue
                )
        
        return edited_article

    async def _apply_grammar_fix(self, text: str, issue: Dict) -> str:
        """Apply a grammar fix to text."""
        if issue.get("auto_fix"):
            return issue["auto_fix"]
        
        # Use LLM to generate fix
        fix_prompt = f"Fix the following grammar issue: {issue['description']}\nText: {text}"
        fixed_text = await self.llm.generate(fix_prompt)
        return fixed_text.strip()

    async def _improve_content(self, article: Dict, issues: List[Dict]) -> Dict:
        """Improve content based on identified issues."""
        improved_article = article.copy()
        
        # Group issues by section
        issues_by_section = self._group_issues_by_section(issues)
        
        # Improve each section
        for section_id, section_issues in issues_by_section.items():
            if section_id == "title":
                improved_article["title"] = await self._improve_section_content(
                    improved_article["title"],
                    section_issues
                )
            elif section_id.startswith("section_"):
                idx = int(section_id.split("_")[1])
                improved_article["sections"][idx]["content"] = \
                    await self._improve_section_content(
                        improved_article["sections"][idx]["content"],
                        section_issues
                    )
        
        return improved_article

    async def _assess_quality(self, article: Dict) -> float:
        """Assess the overall quality of the article."""
        scores = {
            "grammar": await self.grammar_checker.get_score(article),
            "style": await self.style_checker.get_score(article),
            "content": await self.content_analyzer.get_score(article),
            "readability": await self._calculate_readability(article)
        }
        
        weights = {
            "grammar": 0.3,
            "style": 0.2,
            "content": 0.3,
            "readability": 0.2
        }
        
        return sum(score * weights[category] for category, score in scores.items())

    def _format_issues(self, location: str, issues: List[Dict]) -> List[Dict]:
        """Format issues with location information."""
        return [{
            **issue,
            "location": location
        } for issue in issues]

    def _group_issues_by_section(self, issues: List[Dict]) -> Dict[str, List[Dict]]:
        """Group issues by their section location."""
        grouped = {}
        for issue in issues:
            location = issue["location"]
            if location not in grouped:
                grouped[location] = []
            grouped[location].append(issue)
        return grouped

    def _create_editing_metadata(self, message: Message) -> Dict:
        """Create metadata about the editing process."""
        return {
            "editor_version": self.config.get("editor.version", "1.0.0"),
            "timestamp": datetime.now().isoformat(),
            "original_article_id": message.content["draft_article"]["id"]
        }
