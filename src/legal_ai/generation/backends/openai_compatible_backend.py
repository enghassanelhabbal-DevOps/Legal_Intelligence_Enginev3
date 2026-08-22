"""openai_compatible_backend.py — Remote LLM backend for the generation adapter.

This is the missing piece flagged in the architecture review: `LLMManager`
could fall back from Qwen, but the only fallback implementation
(`llm_backend_template.ExampleLocalLLM`) raised `NotImplementedError`. That
meant any environment without a working local Qwen install (CPU-only dev
machines, Streamlit Cloud, CI) had NO working generation path.

Works with:
  - OpenAI directly (base_url defaults to https://api.openai.com/v1)
  - Google Gemini's OpenAI-compatible endpoint (set base_url accordingly)
  - Any self-hosted OpenAI-compatible server (Ollama, vLLM, text-generation-inference)

This backend is intentionally the ONLY place in the codebase that builds an
Authorization header and calls a third-party completions API — the previous
implementation duplicated this logic three times (once per provider) inside
the Streamlit UI, bypassing the adapter entirely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests

from src.legal_ai.core.exceptions import GenerationError


@dataclass
class OpenAICompatibleConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_s: int = 60
    extra_headers: dict[str, str] = field(default_factory=dict)


class OpenAICompatibleBackend:
    """LLMBackend implementation for any OpenAI-compatible /chat/completions API."""

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config
        self._loaded = False

    def load(self) -> None:
        if not self.config.api_key:
            raise GenerationError(
                "OpenAICompatibleBackend requires an api_key (set via config, "
                "OPENAI_API_KEY env var, or Streamlit secrets)."
            )
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate(self, query: str, context: str) -> str:
        if not self._loaded:
            self.load()

        system_prompt = (
            "أنت نظام للبحث القانوني. استخدم فقط النصوص القانونية المقدمة في 'السياق'. "
            "لا تخترع مواداً أو أرقام مواد أو أحكامًا. لكل استنتاج، قدم إشارة مصدرية. "
            "إذا كان الدليل غير كافٍ، أبلغ بوضوح 'insufficient evidence'. "
            "Return your answer as plain text grounded strictly in the provided context."
        )
        user_prompt = f"السياق القانوني:\n{context}\n\nسؤال المستخدم:\n{query}"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        try:
            response = requests.post(url, headers=headers, json=body, timeout=self.config.timeout_s)
        except requests.RequestException as exc:
            raise GenerationError(f"Remote LLM request failed: {exc}") from exc

        if not response.ok:
            raise GenerationError(f"Remote LLM returned {response.status_code}: {response.text[:300]}")

        try:
            data = response.json()
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise GenerationError(f"Unexpected response shape from remote LLM: {exc}") from exc

    def info(self) -> dict[str, Any]:
        return {
            "backend": "openai_compatible",
            "model": self.config.model,
            "base_url": self.config.base_url,
            "loaded": self._loaded,
        }


__all__ = ["OpenAICompatibleBackend", "OpenAICompatibleConfig"]
