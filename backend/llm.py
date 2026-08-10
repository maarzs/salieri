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


class LLMUnavailableError(RuntimeError):
    """
    Raised when the LLM engine has no usable client.

    Carries a message written for the end user (missing API key, missing
    package, unknown provider) so the server can forward it straight to the UI.
    """


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
        # When the client cannot be built, this holds a human-readable reason
        # that is surfaced to the UI instead of crashing the connection.
        self.init_error: str | None = None
        self._init_client()

    @property
    def is_ready(self) -> bool:
        """True when the engine has a usable client and can serve requests."""
        return self._client is not None and self.init_error is None

    def _init_client(self):
        """
        Initialize the appropriate client based on provider.

        Never raises: a failure here is recorded in ``self.init_error`` so the
        server can keep running and report a helpful message to the user
        (matching how the memory/STT/TTS subsystems degrade gracefully).
        """
        self.init_error = None

        if self.provider == "ollama":
            try:
                import ollama
                self._client = ollama.AsyncClient(host=self.ollama_host)
                logger.info(f"LLM: Ollama client initialized (model: {self.model})")
            except ImportError:
                self._client = None
                self.init_error = (
                    "The 'ollama' package is not installed. "
                    "Run: pip install ollama  (or switch provider to 'openai' in Settings)."
                )
                logger.warning("LLM unavailable: %s", self.init_error)
            except Exception as e:
                self._client = None
                self.init_error = f"Could not initialize Ollama client: {e}"
                logger.warning("LLM unavailable: %s", self.init_error)

        elif self.provider == "openai":
            try:
                from openai import AsyncOpenAI
            except ImportError:
                self._client = None
                self.init_error = (
                    "The 'openai' package is not installed. "
                    "Run: pip install -r backend/requirements.txt"
                )
                logger.warning("LLM unavailable: %s", self.init_error)
                return

            if not self.api_key:
                self._client = None
                self.init_error = (
                    "No API key configured. Open Settings and add your API key, "
                    "or set OPENAI_API_KEY in backend/.env"
                )
                logger.warning("LLM unavailable: %s", self.init_error)
                return

            try:
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                    logger.info(
                        f"LLM: OpenAI-compatible client -> {self.base_url} "
                        f"(model: {self.model})"
                    )
                else:
                    logger.info(
                        f"LLM: OpenAI client initialized (model: {self.model})"
                    )
                self._client = AsyncOpenAI(**kwargs)
            except Exception as e:
                self._client = None
                self.init_error = f"Could not initialize the API client: {e}"
                logger.warning("LLM unavailable: %s", self.init_error)

        else:
            self._client = None
            self.init_error = (
                f"Unknown LLM provider '{self.provider}'. "
                "Expected 'ollama' or 'openai'."
            )
            logger.warning("LLM unavailable: %s", self.init_error)

    def _guard_ready(self):
        """
        Raise a clear, user-facing error when the engine isn't usable.

        Without this, an un-initialized 'openai' provider would silently fall
        through to the Ollama HTTP fallback and surface a misleading
        "connection refused to localhost:11434" instead of the real cause.
        """
        if self.init_error:
            raise LLMUnavailableError(self.init_error)

    async def chat(self, messages: list[dict]) -> str:
        """Generate a complete response from a message array (non-streaming)."""
        self._guard_ready()

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
        self._guard_ready()

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
        if self.init_error:
            return False

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