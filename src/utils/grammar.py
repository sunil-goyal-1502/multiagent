from typing import Dict, List, Optional
import logging
import re
from dataclasses import dataclass
import spacy
from nltk.tokenize import sent_tokenize
import language_tool_python

from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class GrammarIssue:
    category: str
    message: str
    context: str
    suggestion: Optional[str]
    position: Dict[str, int]
    severity: str

class GrammarChecker:
    def __init__(self, config: Config):
        self.config = config
        self.language = config.get("editor.language", "en-US")
        self.tool = language_tool_python.LanguageTool(self.language)
        self.nlp = spacy.load("en_core_web_sm")
        self.issue_history = []

    async def check_text(self, text: str) -> List[GrammarIssue]:
        """Check text for grammar issues."""
        try:
            # Get LanguageTool matches
            matches = self.tool.check(text)
            
            # Convert matches to GrammarIssue objects
            issues = []
            for match in matches:
                issue = await self._create_grammar_issue(match, text)
                if self._should_report_issue(issue):
                    issues.append(issue)
                    
            # Add to issue history
            self.issue_history.extend(issues)
            
            return issues
            
        except Exception as e:
            logger.error(f"Grammar check error: {e}")
            return []

    async def _create_grammar_issue(
        self,
        match: Any,
        text: str
    ) -> GrammarIssue:
        """Create GrammarIssue from LanguageTool match."""
        return GrammarIssue(
            category=match.category,
            message=match.message,
            context=text[match.offset:match.offset + match.errorLength],
            suggestion=match.replacements[0] if match.replacements else None,
            position={
                "offset": match.offset,
                "length": match.errorLength
            },
            severity=self._determine_severity(match)
        )

    def _determine_severity(self, match: Any) -> str:
        """Determine issue severity."""
        category_severity = {
            "TYPOS": "low",
            "PUNCTUATION": "low",
            "GRAMMAR": "medium",
            "STYLE": "low",
            "CASING": "low",
            "COLLOCATIONS": "medium",
            "CONFUSED_WORDS": "high",
            "REDUNDANCY": "low",
            "TYPOGRAPHY": "low",
            "MISC": "low"
        }
        
        # Get base severity from category
        severity = category_severity.get(match.category, "medium")
        
        # Adjust based on rule ID
        if "CONFUSION_RULE" in match.ruleId:
            severity = "high"
        elif "AGREEMENT" in match.ruleId:
            severity = "medium"
            
        return severity

    def _should_report_issue(self, issue: GrammarIssue) -> bool:
        """Determine if issue should be reported based on configuration."""
        # Check severity threshold
        min_severity = self.config.get("editor.grammar.min_severity", "low")
        severity_levels = {"low": 0, "medium": 1, "high": 2}
        
        if severity_levels[issue.severity] < severity_levels[min_severity]:
            return False
            
        # Check category filters
        excluded_categories = self.config.get(
            "editor.grammar.excluded_categories",
            []
        )
        if issue.category in excluded_categories:
            return False
            
        return True

    async def get_suggestions(self, text: str) -> Dict:
        """Get improvement suggestions for text."""
        doc = self.nlp(text)
        
        return {
            "sentence_structure": await self._analyze_sentence_structure(doc),
            "readability": await self._analyze_readability(doc),
            "vocabulary": await self._analyze_vocabulary(doc),
            "style": await self._analyze_style(doc)
        }

    async def _analyze_sentence_structure(self, doc: Any) -> Dict:
        """Analyze sentence structure."""
        sentences = list(doc.sents)
        
        return {
            "average_length": sum(len(sent) for sent in sentences) / len(sentences),
            "complexity_score": self._calculate_complexity_score(sentences),
            "suggestions": await self._get_structure_suggestions(sentences)
        }

    async def _analyze_readability(self, doc: Any) -> Dict:
        """Analyze text readability."""
        text = doc.text
        sentences = sent_tokenize(text)
        words = [token.text for token in doc if not token.is_punct]
        syllables = sum(self._count_syllables(word) for word in words)
        
        # Calculate various readability scores
        flesch_score = self._calculate_flesch_score(
            len(sentences),
            len(words),
            syllables
        )
        
        return {
            "flesch_score": flesch_score,
            "grade_level": self._calculate_grade_level(
                len(sentences),
                len(words),
                syllables
            ),
            "suggestions": self._get_readability_suggestions(flesch_score)
        }

    async def _analyze_vocabulary(self, doc: Any) -> Dict:
        """Analyze vocabulary usage."""
        words = [token.text.lower() for token in doc if token.is_alpha]
        unique_words = set(words)
        
        return {
            "unique_words": len(unique_words),
            "vocabulary_richness": len(unique_words) / len(words),
            "advanced_words": self._count_advanced_words(words),
            "suggestions": await self._get_vocabulary_suggestions(doc)
        }

    async def _analyze_style(self, doc: Any) -> Dict:
        """Analyze writing style."""
        return {
            "voice": self._analyze_voice(doc),
            "formality": self._analyze_formality(doc),
            "conciseness": self._analyze_conciseness(doc),
            "suggestions": await self._get_style_suggestions(doc)
        }

    def _calculate_complexity_score(self, sentences: List) -> float:
        """Calculate sentence complexity score."""
        scores = []
        for sent in sentences:
            # Count clauses, phrases, and modifiers
            clause_count = len([token for token in sent 
                              if token.dep_ in ["ccomp", "xcomp", "advcl"]])
            phrase_count = len([token for token in sent 
                              if token.dep_ in ["prep", "npadvmod", "pobj"]])
            
            score = 1.0 + (0.1 * clause_count) + (0.05 * phrase_count)
            scores.append(score)
            
        return sum(scores) / len(scores)

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word."""
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        
        # Handle special cases
        if word.endswith("e"):
            word = word[:-1]
            
        prev_char_is_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_char_is_vowel:
                count += 1
            prev_char_is_vowel = is_vowel
            
        return max(1, count)

    def _calculate_flesch_score(
        self,
        num_sentences: int,
        num_words: int,
        num_syllables: int
    ) -> float:
        """Calculate Flesch Reading Ease score."""
        if num_sentences == 0 or num_words == 0:
            return 0.0
            
        words_per_sentence = num_words / num_sentences
        syllables_per_word = num_syllables / num_words
        
        return 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)

    def _calculate_grade_level(
        self,
        num_sentences: int,
        num_words: int,
        num_syllables: int
    ) -> float:
        """Calculate approximate grade level."""
        if num_sentences == 0 or num_words == 0:
            return 0.0
            
        words_per_sentence = num_words / num_sentences
        syllables_per_word = num_syllables / num_words
        
        return 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

    def _count_advanced_words(self, words: List[str]) -> int:
        """Count advanced vocabulary words."""
        # This is a simplified implementation
        # In practice, you'd want a comprehensive dictionary of advanced words
        advanced_word_patterns = [
            r'\w{12,}',  # Words with 12+ characters
            r'\w+tion\b',  # Words ending in 'tion'
            r'\w+ology\b',  # Words ending in 'ology'
            r'\w+esque\b',  # Words ending in 'esque'
        ]
        
        count = 0
        for word in words:
            for pattern in advanced_word_patterns:
                if re.match(pattern, word, re.IGNORECASE):
                    count += 1
                    break
                    
        return count

    def _analyze_voice(self, doc: Any) -> Dict:
        """Analyze active vs passive voice."""
        sentences = list(doc.sents)
        passive_count = 0
        active_count = 0
        
        for sent in sentences:
            if self._is_passive_voice(sent):
                passive_count += 1
            else:
                active_count += 1
                
        total = passive_count + active_count
        return {
            "active_ratio": active_count / total if total > 0 else 0,
            "passive_ratio": passive_count / total if total > 0 else 0
        }

    def _analyze_formality(self, doc: Any) -> Dict:
        """Analyze text formality."""
        formal_indicators = 0
        informal_indicators = 0
        
        for token in doc:
            if self._is_formal_indicator(token):
                formal_indicators += 1
            if self._is_informal_indicator(token):
                informal_indicators += 1
                
        total = formal_indicators + informal_indicators
        return {
            "formality_score": formal_indicators / total if total > 0 else 0.5,
            "formal_indicators": formal_indicators,
            "informal_indicators": informal_indicators
        }

    def _analyze_conciseness(self, doc: Any) -> Dict:
        """Analyze text conciseness."""
        words = [token.text for token in doc if not token.is_punct]
        content_words = [token.text for token in doc if token.is_alpha 
                        and not token.is_stop]
        
        return {
            "content_density": len(content_words) / len(words) if words else 0,
            "redundant_phrases": self._find_redundant_phrases(doc),
            "wordiness_score": self._calculate_wordiness(doc)
        }

    def _is_passive_voice(self, sent: Any) -> bool:
        """Check if sentence is in passive voice."""
        # Look for passive voice pattern: be + past participle
        for token in sent:
            if (token.dep_ == "auxpass" or 
                (token.dep_ == "aux" and token.head.tag_ == "VBN")):
                return True
        return False

    def _is_formal_indicator(self, token: Any) -> bool:
        """Check if token indicates formal language."""
        formal_patterns = [
            r'\w+ly\b',  # Adverbs
            r'\w+whom\b',  # Formal pronouns
            r'\w+therefore\b',  # Formal conjunctions
            r'\w+furthermore\b',
            r'\w+nevertheless\b'
        ]
        
        return any(re.match(pattern, token.text, re.IGNORECASE) 
                  for pattern in formal_patterns)

    def _is_informal_indicator(self, token: Any) -> bool:
        """Check if token indicates informal language."""
        informal_patterns = [
            r'\w+gonna\b',
            r'\w+wanna\b',
            r'\w+dunno\b',
            r'\blol\b',
            r'\bbtw\b'
        ]
        
        return any(re.match(pattern, token.text, re.IGNORECASE) 
                  for pattern in informal_patterns)

    def _find_redundant_phrases(self, doc: Any) -> List[Dict]:
        """Find redundant phrases in text."""
        redundant_patterns = [
            (r'absolutely essential', 'essential'),
            (r'basic fundamentals', 'fundamentals'),
            (r'completely filled', 'filled'),
            (r'end result', 'result'),
            (r'future plans', 'plans')
        ]
        
        findings = []
        text = doc.text
        for pattern, suggestion in redundant_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append({
                    "phrase": match.group(),
                    "suggestion": suggestion,
                    "position": {
                        "start": match.start(),
                        "end": match.end()
                    }
                })
                
        return findings

    def _calculate_wordiness(self, doc: Any) -> float:
        """Calculate wordiness score."""
        sentences = list(doc.sents)
        if not sentences:
            return 0.0
            
        total_words = sum(len([token for token in sent if not token.is_punct]) 
                         for sent in sentences)
        average_words = total_words / len(sentences)
        
        # Score increases with sentence length
        # Optimal length is considered to be around 15-20 words
        return max(0, (average_words - 15) / 5)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.tool.close()
        self.issue_history = []
