# app/services/ai_service.py
# PasekSaaS — Azure OpenAI Service with Retry
# ──────────────────────────────────────────────────────
"""
Wrapper around the Azure OpenAI client with:
  - Retry (exponential backoff, max 3 attempts)
  - Timeout protection
  - Structured error classification
"""

import logging

from openai import AzureOpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Exceptions worth retrying (transient errors)
RETRYABLE_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)


class AIService:
    """Manages the Azure OpenAI client and chat completion calls."""

    def __init__(self):
        self._client: AzureOpenAI | None = None
        self._deployment: str = ""
        self._max_tokens: int = 800
        self._temperature: float = 0.7
        self._timeout: int = 30

    def initialize(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        max_tokens: int = 800,
        temperature: float = 0.7,
        timeout: int = 30,
    ) -> None:
        """Initialize the Azure OpenAI client. Called once during app startup."""
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            timeout=timeout,
        )
        self._deployment = deployment
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        logger.info(
            "✅ Azure OpenAI ready. Deployment=%s, APIVersion=%s",
            deployment,
            api_version,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_completion(self, messages: list[dict]) -> str:
        """
        Internal: Make a chat completion call with retry logic.
        
        Note: The OpenAI SDK is synchronous, so we call this via
        asyncio.to_thread() from the async route handler.
        """
        if not self._client:
            raise RuntimeError("AI client not initialized. Call initialize() first.")

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""

    async def chat(self, messages: list[dict]) -> str:
        """
        Send messages to Azure OpenAI and get a completion.
        
        Runs the synchronous SDK call in a thread pool to avoid
        blocking the FastAPI event loop.
        
        Args:
            messages: List of message dicts [{"role": "...", "content": "..."}]
        
        Returns:
            AI reply text
        
        Raises:
            Exception: On permanent failures after retries exhausted
        """
        import asyncio
        return await asyncio.to_thread(self._call_completion, messages)

    @property
    def deployment_name(self) -> str:
        return self._deployment

    @property
    def is_ready(self) -> bool:
        return self._client is not None


# Global singleton — initialized in lifespan
ai_service = AIService()
