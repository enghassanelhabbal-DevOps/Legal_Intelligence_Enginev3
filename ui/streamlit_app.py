"""ui/streamlit_app.py — The ONE canonical Streamlit UI.

Architecture decision (see the accompanying review report, section "Streamlit
Strategy — architecture improvement"): this repository previously had TWO
Streamlit UIs — a 995-line `app.py` that re-implemented BM25 search and
provider calls directly in the UI, and this thin file, which only worked if
a FastAPI backend was separately deployed. Deploying only `ui/` meant the UI
was unusable without extra infrastructure; deploying only `app.py` meant
duplicated, drifting business logic (which is exactly what caused the
original "answers don't reflect my dataset" bug in this project's history).

This file resolves that by supporting two modes, chosen automatically, with
retrieval/generation logic living in EXACTLY ONE place either way
(`src/legal_ai/services/query_service.py`):

  - Remote mode  (preferred — matches ARCHITECTURE_CONTRACT.md): if
    LEGAL_API_URL is configured, every query is a plain HTTP call to the
    FastAPI service. The UI contains zero retrieval/generation code.

  - Embedded mode (fallback for single-service deployments, e.g. Streamlit
    Cloud with no separately hosted API): the UI imports `QueryService`
    directly and calls `.answer()` in-process — the SAME orchestration
    method the API calls. No BM25/FAISS/prompt code is duplicated here; the
    UI only ever calls that one function.

The UI never talks to OpenAI/Gemini/etc. directly — API keys entered here
are passed into `QueryService`'s `LLMManager` config exactly as they would
be in an environment variable, so there is a single implementation of
"call a remote LLM" too (`generation/backends/openai_compatible_backend.py`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API_URL = os.getenv("LEGAL_API_URL", "").strip()
LOCAL_RUNTIME_ALLOWED = os.getenv("ALLOW_LOCAL_MODEL_RUNTIME", "0").strip().lower() in {"1", "true", "yes", "on"}
DOCUMENTS_PATH = ROOT / os.getenv("DOCUMENTS_PATH", "legal_documents.json")


def _get_secret(name: str, default: str = "") -> str:
    """Resolve config the same way everywhere: Streamlit secrets -> env -> default.

    Streamlit does NOT mirror `.streamlit/secrets.toml` into os.environ
    automatically — code that only checks os.getenv(...) silently ignores
    keys configured in Streamlit Cloud's "Secrets" panel. This is the single
    place that resolves that ambiguity for the whole UI.
    """
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            value = st.secrets[name]
            if value:
                return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


st.set_page_config(page_title="Legal Intelligence Engine", layout="wide")
st.title("⚖️ Legal Intelligence Engine")
st.caption("Retrieval + evidence + grounded answer generation — Arabic legal corpus")

# ---------------------------------------------------------------------------
# Sidebar: mode banner + (embedded-mode only) provider configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    if API_URL:
        st.success(f"Remote API mode\n\n{API_URL}")
        provider_config: dict[str, Any] = {}
    else:
        st.info("Embedded mode — no LEGAL_API_URL configured.\nRunning retrieval + generation in-process.")
        provider = st.selectbox(
            "LLM provider",
            ["OpenAI-compatible (OpenAI / Gemini / self-hosted)"]
            + (["Local Qwen"] if LOCAL_RUNTIME_ALLOWED else []),
            index=0,
        )
        if provider.startswith("OpenAI"):
            api_key = st.text_input(
                "API key", value=_get_secret("OPENAI_API_KEY") or _get_secret("GOOGLE_API_KEY"),
                type="password",
            )
            base_url = st.text_input(
                "Base URL", value=_get_secret("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
            model = st.text_input("Model", value=_get_secret("OPENAI_MODEL", "gpt-4o-mini"))
            provider_config = {
                "backend": "openai_compatible",
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
            }
        else:
            provider_config = {"backend": "qwen_transformers"}

        top_k = st.slider("Top results", min_value=3, max_value=10, value=5)

    st.markdown("---")
    st.caption(f"Corpus: `{DOCUMENTS_PATH.name}`" + (" (found)" if DOCUMENTS_PATH.exists() else " ⚠️ NOT FOUND"))


# ---------------------------------------------------------------------------
# Embedded-mode service (built once per provider config, not per query)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="جاري تجهيز محرك الاسترجاع...")
def _get_embedded_service(llm_backend: str, api_key: str, base_url: str, model: str):
    from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
    from src.legal_ai.services.query_service import QueryService

    documents = __import__("json").loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    llm_config = {"backend": llm_backend}
    if llm_backend == "openai_compatible":
        llm_config.update({"api_key": api_key, "base_url": base_url, "model": model})

    return QueryService(
        documents=documents,
        runtime=RuntimeConfig(device="cpu" if not LOCAL_RUNTIME_ALLOWED else "auto"),
        pipeline_cfg=PipelineConfig(final_k=5),
        artifact_dir=ROOT / "artifacts" / "ui_embedded",
        load_reranker=False,
        llm_config=llm_config,
    )


def _run_remote(query: str, top_k: int) -> dict[str, Any]:
    response = requests.post(API_URL, json={"query": query, "top_k": top_k}, timeout=60)
    if response.status_code != 200:
        return {"answer": None, "error": f"API error {response.status_code}: {response.text[:300]}"}
    return response.json()


def _run_embedded(query: str, top_k: int, config: dict[str, Any]) -> dict[str, Any]:
    if not DOCUMENTS_PATH.exists():
        return {"answer": None, "error": f"Corpus file not found at {DOCUMENTS_PATH}."}
    try:
        service = _get_embedded_service(
            config.get("backend", "openai_compatible"),
            config.get("api_key", ""),
            config.get("base_url", ""),
            config.get("model", ""),
        )
        result = service.answer(query, top_k=top_k)
        return {
            "answer": result.answer,
            "citations": result.citations,
            "sources": result.evidence,
            "warnings": result.warnings,
            "timing": result.timing,
        }
    except Exception as exc:  # noqa: BLE001
        return {"answer": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Chat UI
# ---------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for role, message in st.session_state["chat_history"]:
    with st.chat_message(role):
        st.markdown(message)

query = st.chat_input("اكتب سؤالك القانوني هنا... (مثال: ما هي شروط القبض في حالة التلبس؟)")

if query and query.strip():
    st.session_state["chat_history"].append(("user", query))
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("جاري استرجاع السياق القانوني وتوليد الإجابة..."):
            top_k = st.session_state.get("top_k", 5)
            if API_URL:
                result = _run_remote(query, top_k=5)
            else:
                result = _run_embedded(query, top_k=top_k if "top_k" in dir() else 5, config=provider_config)

        if result.get("error"):
            st.error(result["error"])
            answer_text = f"⚠️ {result['error']}"
        else:
            answer_text = result.get("answer") or "لم يتم توليد إجابة."
            st.markdown(answer_text)

            citations = result.get("citations") or []
            sources = result.get("sources") or citations
            if sources:
                with st.expander(f"📚 المراجع ({len(sources)})"):
                    for item in sources[:6]:
                        law = item.get("law_name", "غير محدد")
                        article = item.get("article_id", "N/A")
                        text = str(item.get("text") or item.get("content") or "")[:400]
                        st.markdown(f"**{law} / المادة {article}**\n\n{text}")

            warnings = result.get("warnings") or []
            for w in warnings:
                st.caption(f"⚠️ {w}")

            timing = result.get("timing") or {}
            if timing:
                st.caption(
                    f"⏱️ retrieval: {timing.get('retrieval_ms', 0):.0f}ms · "
                    f"generation: {timing.get('generation_ms', 0):.0f}ms · "
                    f"total: {timing.get('total_ms', 0):.0f}ms"
                )

        st.session_state["chat_history"].append(("assistant", answer_text))
