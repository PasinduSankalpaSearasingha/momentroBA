import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from core.config import settings

logger = logging.getLogger("LLMClient")

class LLMClient:
    """Zero-dependency OpenAI API client using Python standard library urllib.request."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.temperature = temperature if temperature is not None else settings.openai_temperature
        self.timeout = timeout or settings.request_timeout
        self.endpoint = "https://api.openai.com/v1/chat/completions"

        if not self.api_key:
            logger.warning("No OpenAI API Key found in environment. LLM calls will fail unless configured.")

    def generate_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Calls the OpenAI Chat Completions endpoint with retries and exponential backoff."""
        if not self.api_key:
            raise ValueError(
                "OpenAI API Key is missing. Please set OPEN_AI_KEY or OPENAI_API_KEY in your .env file."
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        
        # Build SSL context
        ctx = ssl.create_default_context()

        max_attempts = settings.max_retries
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as response:
                    body = response.read().decode("utf-8")
                    result = json.loads(body)
                    content = result["choices"][0]["message"]["content"]
                    return content
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.error(f"HTTPError {e.code} on attempt {attempt}/{max_attempts}: {err_body}")
                last_exception = RuntimeError(f"OpenAI API Error {e.code}: {err_body}")

                # Rate limiting or temporary server error
                if e.code in [429, 500, 502, 503, 504]:
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
                    continue
                else:
                    raise last_exception
            except urllib.error.URLError as e:
                logger.error(f"URLError on attempt {attempt}/{max_attempts}: {e.reason}")
                last_exception = RuntimeError(f"Network error connecting to OpenAI: {e.reason}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Unexpected error calling OpenAI API: {e}")
                last_exception = e
                break

        raise last_exception or RuntimeError("Failed to get completion from OpenAI API after retries.")

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Convenience method to request and parse JSON output from the LLM."""
        raw = self.generate_completion(messages=messages, json_mode=True, temperature=temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM response as JSON: {raw}")
            # Attempt to extract JSON from code block if model wrapped it
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
