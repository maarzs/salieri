"""
LLM Engine - Ollama integration with cloud API fallback.

Supports any OpenAI-compatible API (OpenAI, OpenRouter, Groq, DeepSeek, Together, etc.)
Set SALIERI_LLM_PROVIDER=openai and configure API key + base URL.

Environment variables:
  SALIERI_LLM_PROVIDER  - "ollama" (default) or "openai"
  SALIERI_LLM_MODEL     - Model name (default: llama3.2:3b for ollama, gpt-4o-mini for openai)
  OPENAI_API_KEY        - API key for OpenAI-compatible providers
  OPENAI_BASE_URL       - Base URL for OpenAI-compatible providers (optional)
  OLLAMA_HOST           - Ollama host (default: http://localhost:11434)
"""

import os
import logging
from typing import AsyncIterator

logger = logging.getLogger("salieri.llm")


class LLMEngine:
    """LLM interface with Ollama local-first, any OpenAI-compatible API as option."""

    def __init__(self, settings: dict | None = None):
        """Configure from a settings dict when provided, else from env vars.

        Passing settings lets the app reconfigure the provider/base URL/model at
        runtime from the Settings panel without restarting the backend.
        """
        s = settings or {}

        self.provider = s.get("provider") or os.getenv("SALIERI_LLM_PROVIDER", "ollama")
        self.ollama_host = (
            s.get("ollama_host")
            or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        )
        self.api_key = s.get("api_key") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = s.get("base_url") or os.getenv("OPENAI_BASE_URL", "") or None

        default_model = "gpt-4o-mini" if self.provider == "openai" else "llama3.2:3b"
        self.model = s.get("model") or os.getenv("SALIERI_LLM_MODEL", default_model)

        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the appropriate client based on provider."""
        if self.provider == "ollama":
            try:
                import ollama
                self._client = ollama.AsyncClient(host=self.ollama_host)
                logger.info(f"LLM: Ollama client initialized (model: {self.model})")
            except ImportError:
                logger.warning("ollama package not installed, falling back to HTTP")
                self._client = None

        elif self.provider == "openai":
            try:
                from openai import AsyncOpenAI

                api_key = self.api_key
                base_url = self.base_url

                if not api_key:
                    raise ValueError(
                        "OPENAI_API_KEY not set. "
                        "Set it via environment variable or .env file."
                    )

                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                    logger.info(
                        f"LLM: OpenAI-compatible client -> {base_url} "
                        f"(model: {self.model})"
                    )
                else:
                    logger.info(
                        f"LLM: OpenAI client initialized (model: {self.model})"
                    )

                self._client = AsyncOpenAI(**kwargs)

            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
                raise

    async def chat(self, messages: list[dict]) -> str:
        """Generate a complete response from a message array (non-streaming)."""
        if self.provider == "ollama" and self._client:
            response = await self._client.chat(
                model=self.model,
                messages=messages,
            )
            return response["message"]["content"]

        elif self.provider == "openai" and self._client:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""

        else:
            return await self._http_generate(messages)

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Generate a response with streaming chunks from a message array."""
        if self.provider == "ollama" and self._client:
            stream = await self._client.chat(
                model=self.model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

        elif self.provider == "openai" and self._client:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=1024,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    # Some OpenAI-compatible providers emit a final usage-only
                    # chunk with an empty choices array — skip it.
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        else:
            result = await self._http_generate(messages)
            yield result

    async def _http_generate(self, messages: list[dict]) -> str:
        """Fallback: use Ollama HTTP API with aiohttp."""
        import aiohttp
        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                return data.get("message", {}).get("content", "")

    async def list_models(self) -> list[str]:
        """Fetch available model names from the configured provider.

        Returns an empty list if the endpoint can't be reached, so the UI can
        fall back to free-text model entry instead of blocking the user.
        """
        try:
            if self.provider == "openai":
                if not self._client:
                    return []
                resp = await self._client.models.list()
                return sorted(m.id for m in resp.data)

            import aiohttp
            url = f"{self.ollama_host}/api/tags"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        return []
                    data = await r.json()
                    return sorted(
                        m.get("name", "") for m in data.get("models", []) if m.get("name")
                    )
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []

    async def check_health(self) -> bool:
        """Check if the LLM is available."""
        if self.provider == "openai" and self._client:
            return True

        try:
            import aiohttp
            url = f"{self.ollama_host}/api/tags"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return resp.status == 200
        except Exception:
            return False