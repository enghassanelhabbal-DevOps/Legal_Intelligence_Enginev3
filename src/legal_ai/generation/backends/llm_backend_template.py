"""llm_backend_template.py — Reference template for adding a NEW backend.

This file is NOT loaded by `LLMManager` (see generation/manager.py, which
selects between `qwen_transformers_backend` and `openai_compatible_backend`).
Copy this pattern to add a third backend (e.g. an Ollama-specific client);
then add a `_try_load_<name>()` method to `LLMManager` following the same
shape as `_try_load_qwen` / `_try_load_openai_compatible`.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMBackend(Protocol):
    def generate(self, query: str, context: str) -> str: ...


class ExampleLocalLLM:
    """Adapter interface only. Replace with your own backend implementation."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def generate(self, query: str, context: str) -> str:
        # Implement your selected LLM backend here.
        # Return only the final grounded answer string.
        raise NotImplementedError("This is a template, not a usable backend. See module docstring.")
