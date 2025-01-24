from typing import Dict, List, Optional, Union
import logging
import asyncio
from datetime import datetime
import json
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Config

logger = logging.getLogger(__name__)

class LLMInterface:
    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.get("llm.api_key")
        self.model = config.get("llm.model", "gpt-4")
        self.temperature = config.get("llm.temperature", 0.7)
        self.max_tokens = config.get("llm.max_tokens", 2000)
        self.request_history = []
        
        openai.api_key = self.api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate text using the LLM."""
        try:
            messages = []
            
            # Add system prompt if provided
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # Add user prompt
            messages.append({
                "role": "user",
                "content": prompt
            })

            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )

            # Log request
            self._log_request(prompt, response)

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    async def generate_with_context(
        self,
        prompt: str,
        context: Union[str, List[str]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate text with additional context."""
        if isinstance(context, list):
            context = "\n".join(context)

        full_prompt = f"Context:\n{context}\n\nPrompt:\n{prompt}"
        return await self.generate(full_prompt, system_prompt=system_prompt)

    async def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text."""
        prompt = f"""Analyze the sentiment of the following text and return a JSON with:
        - score (0-1, where 0 is very negative and 1 is very positive)
        - primary_emotion
        - key_phrases (list of important phrases that contribute to the sentiment)

        Text: {text}"""

        response = await self.generate(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse sentiment analysis response")
            return {
                "score": 0.5,
                "primary_emotion": "neutral",
                "key_phrases": []
            }

    async def extract_key_points(self, text: str) -> List[Dict]:
        """Extract key points from text."""
        prompt = f"""Extract the main points from the following text as a JSON list with:
        - point (the key point)
        - confidence (0-1)
        - supporting_text (relevant quote from original text)

        Text: {text}"""

        response = await self.generate(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse key points response")
            return []

    async def improve_text(
        self,
        text: str,
        style_guide: Optional[Dict] = None,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """Improve text based on style guide and focus areas."""
        prompt_parts = [f"Improve the following text:"]
        
        if style_guide:
            prompt_parts.append(f"Style Guide:\n{json.dumps(style_guide, indent=2)}")
        
        if focus_areas:
            prompt_parts.append(f"Focus on: {', '.join(focus_areas)}")
        
        prompt_parts.append(f"Text:\n{text}")
        
        return await self.generate("\n\n".join(prompt_parts))

    def _log_request(self, prompt: str, response: Dict) -> None:
        """Log LLM request and response."""
        self.request_history.append({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "model": self.model,
            "response": response,
            "tokens": {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens
            }
        })

    async def get_token_count(self, text: str) -> int:
        """Estimate token count for text."""
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4

    def get_usage_stats(self) -> Dict:
        """Get usage statistics."""
        if not self.request_history:
            return {}

        total_tokens = 0
        total_requests = len(self.request_history)
        token_distribution = {
            "prompt": 0,
            "completion": 0
        }

        for request in self.request_history:
            tokens = request["tokens"]
            total_tokens += tokens["total"]
            token_distribution["prompt"] += tokens["prompt"]
            token_distribution["completion"] += tokens["completion"]

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "average_tokens_per_request": total_tokens / total_requests,
            "token_distribution": {
                "prompt": token_distribution["prompt"] / total_tokens,
                "completion": token_distribution["completion"] / total_tokens
            }
        }

    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Save request history if needed
        if self.config.get("llm.save_history", False):
            history_file = self.config.get("llm.history_file", "llm_history.json")
            try:
                with open(history_file, 'w') as f:
                    json.dump(self.request_history, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save LLM history: {e}")

        # Clear memory
        self.request_history = []
