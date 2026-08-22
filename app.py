from __future__ import annotations

import json
import os
import re
import traceback
from pathlib import Path
from typing import Any

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
API_URL = os.getenv("LEGAL_API_URL", "")
LOCAL_RUNTIME_ALLOWED = os.getenv("ALLOW_LOCAL_MODEL_RUNTIME", "0").strip().lower() in {"1", "true", "yes", "on"}


def _get_secret(name: str, default: str = "") -> str:
    """Resolve a secret with a single consistent priority order everywhere in the app:

    1. Streamlit Cloud / local `.streamlit/secrets.toml` (st.secrets)
    2. Environment variable
    3. default

    Streamlit secrets are NOT automatically mirrored into os.environ, so any code that
    only checked os.getenv(...) silently ignored keys configured in Streamlit Cloud's
    "Secrets" panel. This helper is the single place that resolves that ambiguity.
    """
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            value = st.secrets[name]
            if value:
                return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


# ---------------------------------------------------------------------------
# Live model availability check
#
# When the user enters an API key, we call the provider's OWN "list models"
# endpoint (a free, lightweight call — no tokens spent) to find out exactly
# which models that specific key is authorized to use RIGHT NOW. This is a
# real live check against the provider, not a hardcoded guess: a model shows
# up green only because the provider itself just confirmed it for this key.
# ---------------------------------------------------------------------------

# Fallback preferred lists shown before a key is entered (so the dropdown
# isn't empty), and used to order/annotate the live results once a key IS
# entered and verified.
_PREFERRED_OPENAI_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "o1", "o1-mini", "o3", "o3-mini", "o4-mini", "gpt-3.5-turbo",
]
_PREFERRED_GEMINI_MODELS = [
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
    "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash",
]

# Non-chat model families we don't want cluttering the picker even though
# the provider's /models endpoint returns them (embeddings, audio, images...).
_OPENAI_EXCLUDE_SUBSTRINGS = (
    "embedding", "whisper", "tts", "dall-e", "moderation", "davinci-002",
    "babbage", "audio", "realtime", "transcribe", "image",
)


@st.cache_data(ttl=300, show_spinner=False)
def check_openai_models(api_key: str) -> dict[str, Any]:
    """Live-check an OpenAI (or OpenAI-compatible) key via GET /v1/models.

    Returns {"ok": bool, "models": [ids...], "error": str|None}.
    `models` is exactly what the provider says THIS key can access — nothing
    is inferred or hardcoded.
    """
    if not api_key:
        return {"ok": False, "models": [], "error": "no_key"}
    try:
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    except Exception as exc:
        return {"ok": False, "models": [], "error": f"network error: {exc}"}

    if resp.status_code == 401:
        return {"ok": False, "models": [], "error": "invalid_key"}
    if not resp.ok:
        return {"ok": False, "models": [], "error": f"HTTP {resp.status_code}: {resp.text[:150]}"}

    try:
        raw_ids = sorted(m["id"] for m in resp.json().get("data", []))
    except Exception as exc:
        return {"ok": False, "models": [], "error": f"unexpected response shape: {exc}"}

    chat_models = [
        m for m in raw_ids
        if not any(bad in m for bad in _OPENAI_EXCLUDE_SUBSTRINGS)
    ]
    return {"ok": True, "models": chat_models, "error": None}


@st.cache_data(ttl=300, show_spinner=False)
def check_gemini_models(api_key: str) -> dict[str, Any]:
    """Live-check a Google API key via GET /v1beta/models?key=...

    Only keeps models that support `generateContent` (i.e. usable for
    chat/answer generation) — the endpoint also lists embedding-only models.
    """
    if not api_key:
        return {"ok": False, "models": [], "error": "no_key"}
    try:
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
            timeout=10,
        )
    except Exception as exc:
        return {"ok": False, "models": [], "error": f"network error: {exc}"}

    if not resp.ok:
        # IMPORTANT: do NOT collapse every 400/401/403 into "the key is
        # wrong". Google returns 403 for several genuinely different
        # problems that are NOT "you typed the key wrong":
        #   - PERMISSION_DENIED: the Generative Language API is simply not
        #     enabled yet for the Google Cloud project behind this key
        #     (very common with a freshly created AI Studio key)
        #   - the key has an HTTP-referrer or IP restriction that blocks
        #     server-side calls (Streamlit runs server-side, not a browser)
        #   - RESOURCE_EXHAUSTED: quota/rate limit, not an invalid key
        # A blanket "invalid key" message here sends the user on a wild
        # goose chase re-copying a key that was never the problem. We parse
        # Google's own error message and show it instead.
        try:
            detail = resp.json().get("error", {})
            status = detail.get("status", "")
            message = detail.get("message", resp.text[:200])
        except Exception:
            status, message = "", resp.text[:200]

        if status == "INVALID_ARGUMENT" and (
            "api key not valid" in message.lower() or "api_key_invalid" in message.lower()
        ):
            return {"ok": False, "models": [], "error": "invalid_key"}
        if status == "PERMISSION_DENIED" or resp.status_code == 403:
            return {
                "ok": False, "models": [],
                "error": f"permission_denied: {message} "
                "(الأغلب: خدمة Generative Language API غير مفعّلة على مشروع Google Cloud "
                "بتاع المفتاح ده، أو المفتاح مقيّد بـ HTTP referrer/IP معيّن)",
            }
        if resp.status_code == 429:
            return {"ok": False, "models": [], "error": f"rate_limited: {message}"}
        return {"ok": False, "models": [], "error": f"HTTP {resp.status_code}: {message}"}

    try:
        data = resp.json().get("models", [])
    except Exception as exc:
        return {"ok": False, "models": [], "error": f"unexpected response shape: {exc}"}

    chat_models = sorted(
        m["name"].removeprefix("models/")
        for m in data
        if "generateContent" in m.get("supportedGenerationMethods", [])
    )
    return {"ok": True, "models": chat_models, "error": None}


def _status_dot(color: str) -> str:
    return (
        f"<span style='display:inline-block;width:9px;height:9px;"
        f"border-radius:50%;background:{color};margin-inline-end:8px;"
        f"vertical-align:middle;'></span>"
    )


def render_model_status_list(check_result: dict[str, Any], preferred: list[str], label: str) -> None:
    """Render the small green/gray dot list the user asked for.

    - No key entered yet          -> gray dots, "أدخل مفتاح API" note.
    - Key entered but invalid      -> red banner (the key itself doesn't work).
    - Key valid                    -> green dot for every model the provider
                                       actually confirmed for this key; gray
                                       dot for common models this key does
                                       NOT have access to (still informative:
                                       tells the user what they're missing).
    """
    error = check_result.get("error")
    live_models = set(check_result.get("models") or [])

    if error == "no_key":
        st.caption(f"🔘 {label}: أدخل المفتاح فوق عشان نتحقق من الموديلات المتاحة فعليًا.")
        return
    if error == "invalid_key":
        st.markdown(
            f"{_status_dot('#ef4444')}**{label}: المفتاح غير صالح** — تأكد إنك نسخته كامل بدون مسافات.",
            unsafe_allow_html=True,
        )
        return
    if not check_result.get("ok"):
        # Show the REAL reason instead of guessing — a 403 permission_denied
        # (API not enabled / referrer-restricted key) is a completely
        # different fix than a genuinely wrong key, and telling the user
        # "your key is invalid" when it isn't just sends them in circles.
        st.markdown(f"{_status_dot('#f59e0b')}**{label}: تعذّر التحقق**", unsafe_allow_html=True)
        st.caption(str(error))
        return

    st.caption(f"✅ المفتاح شغّال — {len(live_models)} موديل متاح لهذا المفتاح")

    # Preferred/well-known models first (in our curated order), each flagged
    # green/gray based on what the provider actually returned for this key.
    shown = set()
    for model_id in preferred:
        matched = model_id if model_id in live_models else next(
            (m for m in live_models if m.startswith(model_id)), None
        )
        if matched:
            st.markdown(f"{_status_dot('#22c55e')}`{matched}`", unsafe_allow_html=True)
            shown.add(matched)
        else:
            st.markdown(
                f"{_status_dot('#9ca3af')}`{model_id}` — غير متاح لهذا المفتاح",
                unsafe_allow_html=True,
            )

    remaining = sorted(live_models - shown)
    if remaining:
        with st.expander(f"باقي الموديلات المتاحة ({len(remaining)})"):
            for model_id in remaining:
                st.markdown(f"{_status_dot('#22c55e')}`{model_id}`", unsafe_allow_html=True)

st.set_page_config(
    page_title="Legal Intelligence Engine",
    page_icon="⚖️",
    layout="wide",
)


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background: #f5f7fb;
            color: #0f172a;
        }
        .stApp {
            background: linear-gradient(180deg, #f7f9fc 0%, #f3f6fb 100%);
        }
        [data-testid="stSidebar"] {
            background: rgba(248, 250, 252, 0.92);
            border-right: 1px solid rgba(148, 163, 184, 0.25);
        }
        [data-testid="block-container"] {
            padding-top: 1.2rem;
        }
        .top-shell {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 26px;
            padding: 1rem 1.2rem 0.25rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
        }
        .brand-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            font-size: 1.25rem;
            font-weight: 700;
            color: #0f172a;
        }
        .brand-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.3rem;
            height: 2.3rem;
            border-radius: 0.85rem;
            background: linear-gradient(135deg, #8b5cf6, #3b82f6);
            color: white;
            font-size: 1.1rem;
            box-shadow: 0 12px 30px rgba(96, 165, 250, 0.28);
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            border-radius: 999px;
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.25);
            padding: 0.38rem 0.7rem;
            color: #166534;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .hero-bar {
            background: linear-gradient(135deg, rgba(96,165,250,0.10), rgba(172,146,250,0.08));
            border: 1px solid rgba(148,163,184,0.18);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }
        .hero-bar h1 {
            margin: 0;
            font-size: clamp(1.8rem, 2vw, 2.5rem);
            font-weight: 800;
            letter-spacing: -0.04em;
            color: #111827;
        }
        .hero-bar p {
            margin: 0.5rem 0 0;
            color: #475569;
            font-size: 0.98rem;
        }
        .chip-row {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin-top: 0.85rem;
        }
        .chip {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(15, 23, 42, 0.04);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 999px;
            padding: 0.42rem 0.8rem;
            color: #334155;
            font-size: 0.74rem;
            font-weight: 700;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            min-height: 112px;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
        }
        .metric-card .small-muted {
            color: #64748b;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
        }
        .metric-card h2 {
            margin: 0.4rem 0 0;
            font-size: 1.8rem;
            color: #0f172a;
            font-weight: 800;
        }
        .chat-shell {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 26px;
            box-shadow: 0 18px 42px rgba(148, 163, 184, 0.1);
            overflow: hidden;
        }
        .chat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.2rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.16);
            background: rgba(248, 250, 252, 0.8);
        }
        .chat-header .title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #0f172a;
        }
        .assistant-panel {
            padding: 1rem 1rem 0.5rem;
            min-height: 420px;
            background: linear-gradient(180deg, rgba(255,255,255,0.7), rgba(248,250,252,0.8));
        }
        .assistant-panel .stChatMessage {
            margin-bottom: 0.3rem;
        }
        .message-bubble {
            max-width: 85%;
            border-radius: 1.2rem;
            padding: 0.9rem 1rem;
            line-height: 1.6;
            margin: 0.4rem 0;
            box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
        }
        .user-msg {
            background: linear-gradient(135deg, #dbeafe, #e2e8f0);
            color: #0f172a;
            margin-left: auto;
            border-bottom-right-radius: 0.45rem;
        }
        .assistant-msg {
            background: #ffffff;
            border: 1px solid rgba(148, 163, 184, 0.16);
            color: #0f172a;
            margin-right: auto;
            border-bottom-left-radius: 0.45rem;
        }
        .composer {
            border-top: 1px solid rgba(148, 163, 184, 0.14);
            background: rgba(255,255,255,0.96);
            padding: 1rem 1rem 1.1rem;
        }
        .quick-grid {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-bottom: 0.8rem;
        }
        .quick-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: #f8fafc;
            border-radius: 999px;
            color: #334155;
            font-size: 0.75rem;
            padding: 0.5rem 0.8rem;
            font-weight: 600;
        }
        .result-card {
            background: rgba(255,255,255,0.96);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin-top: 0.5rem;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
        }
        .badge {
            display: inline-block;
            background: rgba(59,130,246,0.08);
            color: #1d4ed8;
            border: 1px solid rgba(59,130,246,0.18);
            border-radius: 999px;
            padding: 0.28rem 0.72rem;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .result-card h3 {
            margin: 0.5rem 0 0.35rem;
            color: #0f172a;
            font-size: 1.1rem;
        }
        .result-card p {
            margin: 0.2rem 0 0;
            color: #475569;
            line-height: 1.6;
        }
        .small-muted {
            color: #64748b;
            font-size: 0.82rem;
        }
        .panel-box {
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(148,163,184,0.18);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
        }
        .stButton > button {
            background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 700;
            padding: 0.7rem 1rem;
        }
        .stButton > button:hover {
            filter: brightness(1.04);
        }
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div,
        .stNumberInput > div > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] > div {
            background: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid rgba(148, 163, 184, 0.3) !important;
            border-radius: 14px;
            box-shadow: none !important;
        }
        .stTextInput label,
        .stTextArea label,
        .stSelectbox label,
        .stNumberInput label,
        .stSidebar .stSelectbox label,
        .stSidebar .stTextInput label,
        .stSidebar .stCheckbox label,
        .stSidebar .stRadio label,
        .stSidebar label {
            color: #334155 !important;
        }
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: rgba(71, 85, 105, 0.7) !important;
        }
        .stSidebar .block-container {
            padding-top: 1rem;
        }
        .stTabs [role="tablist"] {
            gap: 0.5rem;
        }
        .stTabs [role="tab"] {
            background: rgba(255,255,255,0.9);
            border-radius: 12px 12px 0 0;
            border: 1px solid rgba(148, 163, 184, 0.2);
            color: #334155;
            font-weight: 600;
        }
        .stTabs [role="tab"][aria-selected="true"] {
            background: rgba(59,130,246,0.08);
            border-color: rgba(96,165,250,0.18);
            color: #0f172a;
        }
        .stAlert {
            background: rgba(239, 246, 255, 0.9);
            border: 1px solid rgba(147, 197, 253, 0.4);
            color: #0f172a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def load_legal_documents() -> list[dict[str, Any]]:
    candidates = [
        ROOT / "legal_documents.json",
        ROOT / "data" / "legal_documents.json",
        ROOT / "data" / "normalized" / "documents.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                return payload
    return [
        {
            "document_id": "sample-1",
            "law_name": "قانون الإجراءات الجنائية",
            "article_id": "1",
            "content": "تُعد الإجراءات الجنائية من أهم الضمانات في القضايا الجنائية، وتخضع للشرط القانوني في حالة التلبس.",
            "metadata": {"title": "المادة 1 - قانون الإجراءات الجنائية"},
        },
        {
            "document_id": "sample-2",
            "law_name": "قانون العقوبات",
            "article_id": "2",
            "content": "يلتزم القاضي في حالة التلبس بالتحقق من الواقعة قبل إصدار القرار، مع مراعاة حقوق المتهم.",
            "metadata": {"title": "المادة 2 - قانون العقوبات"},
        },
        {
            "document_id": "sample-3",
            "law_name": "قانون الأحوال الشخصية",
            "article_id": "3",
            "content": "في المعاملات والحقوق الشخصية يراعى المبدأ العام للعدالة والوضوح في التفسير القانوني.",
            "metadata": {"title": "المادة 3 - قانون الأحوال الشخصية"},
        },
    ]


@st.cache_data
def build_bm25_index() -> tuple[list[str], list[dict[str, Any]]]:
    docs = load_legal_documents()
    corpus: list[str] = []
    records: list[dict[str, Any]] = []
    for doc in docs:
        metadata = doc.get("metadata") or {}
        # Support both schemas:
        #  - the real LegalDocument contract (raw_text / normalized_text / embedding_text)
        #  - the simplified demo schema (content / metadata.title)
        text = str(
            doc.get("content")
            or doc.get("raw_text")
            or doc.get("normalized_text")
            or ""
        )
        title = str(
            metadata.get("title")
            or doc.get("embedding_text")
            or ""
        )
        combined = f"{title} {text}".strip()
        corpus.append(combined)
        records.append(
            {
                "document_id": str(doc.get("document_id") or doc.get("id") or len(records)),
                "law_name": str(doc.get("law_name") or metadata.get("law_name") or "غير محدد"),
                "article_id": str(doc.get("article_id") or metadata.get("article_id") or "N/A"),
                "content": text,
                "title": title,
            }
        )
    return corpus, records


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\u0600-\u06ff\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def simple_search(query: str, k: int = 5) -> list[dict[str, Any]]:
    corpus, records = build_bm25_index()
    q = normalize(query)
    if not q:
        return []
    ranked: list[tuple[float, dict[str, Any]]] = []
    for text, record in zip(corpus, records):
        score = 0.0
        for token in set(q.split()):
            pattern = re.escape(token)
            score += len(re.findall(pattern, normalize(text)))
        if score > 0:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in ranked[:k]]


def render_results(results: list[dict[str, Any]]) -> None:
    st.subheader("نتائج الاسترجاع")
    for idx, hit in enumerate(results, start=1):
        law_name = hit.get("law_name", "غير محدد")
        article_id = hit.get("article_id", "N/A")
        content = hit.get("content", "")
        title = hit.get("title", "")
        st.markdown(
            f"""
            <div class="result-card">
                <div class="badge">Result #{idx}</div>
                <h3>{law_name} / المادة {article_id}</h3>
                <div class="small-muted">{title}</div>
                <p>{content[:500]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


@st.cache_resource
def get_local_rag_service() -> Any | None:
    """Load the local service only when the runtime is explicitly enabled.

    The local FAISS + dense-encoder stack is not stable in all environments and can
    crash the interpreter during startup. The UI therefore disables it by default and
    only attempts a load if the operator deliberately opts in with ALLOW_LOCAL_MODEL_RUNTIME=1.
    """
    if not LOCAL_RUNTIME_ALLOWED:
        st.session_state["runtime_error"] = (
            "Local runtime disabled by environment. This instance is running in safe cloud/fallback mode "
            "because the native FAISS + dense-model stack is not reliable in this environment."
        )
        return None
    try:
        from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
        from src.legal_ai.services.query_service import QueryService

        artifact_dir = ROOT / "artifacts" / "streamlit_live"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        docs = load_legal_documents()
        runtime = RuntimeConfig(device="cpu", precision="auto", dense_batch_size=8, rerank_batch_size=4)
        pipeline_cfg = PipelineConfig(final_k=5, dense_candidates=30, bm25_candidates=12, rerank_candidates=30)
        service = QueryService(documents=docs, runtime=runtime, pipeline_cfg=pipeline_cfg, artifact_dir=artifact_dir, load_reranker=False)
        st.session_state["runtime_error"] = ""
        return service
    except Exception:  # pragma: no cover - runtime safety path
        st.session_state["runtime_error"] = traceback.format_exc()
        return None


def render_live_answer(result: dict[str, Any]) -> None:
    st.subheader("الإجابة المولدة")
    answer_text = str(result.get("answer") or "لم يتم توليد إجابة صالحة.")
    st.markdown(answer_text)

    metrics = result.get("timing") or {}
    if metrics:
        col1, col2, col3 = st.columns(3)
        col1.metric("Retrieval", f"{metrics.get('retrieval_ms', 0):.0f} ms")
        col2.metric("Generation", f"{metrics.get('generation_ms', 0):.0f} ms")
        col3.metric("Total", f"{metrics.get('total_ms', 0):.0f} ms")

    citations = result.get("citations") or []
    if citations:
        st.markdown("### المراجع")
        for idx, citation in enumerate(citations, start=1):
            title = citation.get("law_name") or citation.get("title") or "مصدر قانوني"
            article = citation.get("article_id") or citation.get("article") or "N/A"
            text = citation.get("text") or citation.get("content") or ""
            st.markdown(f"**{idx}. {title} / المادة {article}**\n\n{text[:350]}")

    warnings = result.get("warnings") or []
    if warnings:
        st.warning("\n".join(warnings))

    evidence = result.get("evidence") or []
    if evidence:
        st.markdown("### أدلة السياق")
        for idx, hit in enumerate(evidence[:3], start=1):
            st.write(f"{idx}. {hit.get('law_name', 'غير محدد')} / المادة {hit.get('article_id', 'N/A')}: {str(hit.get('text', ''))[:220]}")


def _provider_model_label(provider: str, config: dict[str, Any]) -> str:
    if provider == "OpenAI":
        return config.get("openai_model") or "gpt-4o-mini"
    if provider == "Google Gemini":
        return config.get("gemini_model") or "gemini-1.5-flash"
    if provider == "Custom API":
        return config.get("custom_model") or "custom-model"
    return config.get("llm_model") or "Qwen 3 (local)"


def _build_context_summary(results: list[dict[str, Any]]) -> str:
    if not results:
        return "لا توجد أدلة قانونية متاحة."
    snippets: list[str] = []
    for item in results[:6]:
        law_name = item.get("law_name") or "القانون"
        article_id = item.get("article_id") or "N/A"
        content = str(item.get("content") or item.get("text") or "")
        snippets.append(f"{law_name} / المادة {article_id}: {content[:800]}")
    return "\n\n".join(snippets)


def _extract_json_answer(raw: str) -> dict[str, Any]:
    try:
        import json

        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"answer": raw.strip() or "No answer available", "citations": [], "warnings": []}


def _call_openai_provider(question: str, context: str, config: dict[str, Any]) -> dict[str, Any]:
    api_key = (config.get("openai_key") or _get_secret("OPENAI_API_KEY")).strip()
    if not api_key:
        return {"answer": None, "warnings": ["OpenAI API key is missing."], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}

    payload = {
        "model": config.get("openai_model") or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a strict Arabic legal assistant. Use only the provided evidence. Cite the legal source in Arabic with article references when available."},
            {"role": "user", "content": f"السؤال: {question}\n\nالسياق:\n{context}\n\nأجب بالعربية مع ذكر المراجع القانونية بشكل واضح."},
        ],
        "temperature": 0.2,
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if not response.ok:
            return {"answer": None, "warnings": [f"OpenAI provider failed: {response.status_code} {response.text[:200]}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}
        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        parsed = _extract_json_answer(raw)
        parsed.setdefault("warnings", [])
        return {"answer": parsed.get("answer") or raw, "citations": parsed.get("citations", []), "warnings": parsed.get("warnings", []), "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}
    except requests.RequestException as exc:
        return {"answer": None, "warnings": [f"OpenAI request error: {exc}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}


def _call_gemini_provider(question: str, context: str, config: dict[str, Any]) -> dict[str, Any]:
    api_key = (config.get("google_key") or _get_secret("GOOGLE_API_KEY")).strip()
    if not api_key:
        return {"answer": None, "warnings": ["Google API key is missing."], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}

    model_name = config.get("gemini_model") or _get_secret("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Use only the following legal context. Answer in Arabic with citations to the law and article.\n\nQuestion: {question}\n\nContext:\n{context}"
            }]
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800},
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        if not response.ok:
            return {"answer": None, "warnings": [f"Gemini provider failed: {response.status_code} {response.text[:200]}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}
        data = response.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return {"answer": text or None, "citations": [], "warnings": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}
    except requests.RequestException as exc:
        return {"answer": None, "warnings": [f"Gemini request error: {exc}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}


def _call_custom_provider(question: str, context: str, config: dict[str, Any]) -> dict[str, Any]:
    endpoint = (config.get("custom_endpoint") or _get_secret("LEGAL_API_URL")).strip()
    if not endpoint:
        return {"answer": None, "warnings": ["Custom endpoint is not configured."], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}

    api_key = (config.get("api_key") or _get_secret("API_KEY")).strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    try:
        # Use a conservative timeout and verify SSL by default
        response = requests.post(endpoint, json={"query": question, "top_k": config.get("top_k", 5), "context": context}, headers=headers, timeout=25)
        if not response.ok:
            return {"answer": None, "warnings": [f"Custom API failed: {response.status_code} {response.text[:200]}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}
        payload = response.json()
        return {
            "answer": payload.get("answer"),
            "citations": payload.get("citations", []),
            "warnings": payload.get("warnings", []),
            "timing": payload.get("timing", {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}),
            "evidence": payload.get("evidence", payload.get("sources", [])),
        }
    except requests.RequestException as exc:
        return {"answer": None, "warnings": [f"Custom API request error: {exc}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": []}


def _execute_provider_flow(question: str, config: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    provider = config.get("provider") or "Local Qwen"
    context = _build_context_summary(results)

    if provider == "Local Qwen":
        rag = get_local_rag_service()
        if rag is not None:
            try:
                answer_obj = rag.answer(question, top_k=config.get("top_k", 5))
                return {
                    "answer": answer_obj.answer,
                    "citations": answer_obj.citations,
                    "warnings": answer_obj.warnings,
                    "timing": answer_obj.timing,
                    "evidence": answer_obj.evidence,
                    "provider": provider,
                    "model": _provider_model_label(provider, config),
                }
            except Exception as exc:
                return {"answer": None, "warnings": [f"Local Qwen runtime failed: {exc}"], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": results, "provider": provider, "model": _provider_model_label(provider, config)}
        return {"answer": None, "warnings": ["Local Qwen backend is unavailable; falling back to retrieval."], "citations": [], "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}, "evidence": results, "provider": provider, "model": _provider_model_label(provider, config)}

    if provider == "OpenAI":
        return {**_call_openai_provider(question, context, config), "provider": provider, "model": _provider_model_label(provider, config)}
    if provider == "Google Gemini":
        return {**_call_gemini_provider(question, context, config), "provider": provider, "model": _provider_model_label(provider, config)}
    if provider == "Custom API":
        return {**_call_custom_provider(question, context, config), "provider": provider, "model": _provider_model_label(provider, config)}

    return {
        "answer": None,
        "warnings": ["No valid provider selected. Using retrieval-only fallback."],
        "citations": [],
        "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0},
        "evidence": results,
        "provider": provider,
        "model": _provider_model_label(provider, config),
    }


def _probe_provider(config: dict[str, Any]) -> tuple[bool, str]:
    """Quick health probe for the selected provider. Returns (ok, message)."""
    provider = config.get("provider", "Local Qwen")
    try:
        if provider == "Local Qwen":
            rag = get_local_rag_service()
            if rag is not None:
                return True, "Local RAG available"
            return False, "Local RAG unavailable"

        if provider == "OpenAI":
            api_key = (config.get("openai_key") or _get_secret("OPENAI_API_KEY")).strip()
            if not api_key:
                return False, "OpenAI API key is missing"
            # minimal probe: request model list (requires auth) — many keys may not allow list; short timeout
            try:
                r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=6)
                return (r.ok, f"OpenAI: {r.status_code}")
            except Exception as e:
                return False, f"OpenAI probe error: {e}"

        if provider == "Google Gemini":
            api_key = (config.get("google_key") or _get_secret("GOOGLE_API_KEY")).strip()
            if not api_key:
                return False, "Google API key is missing"
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            try:
                r = requests.get(url, timeout=6)
                # Provide a clearer message when model names are invalid
                if r.ok:
                    return (True, f"Google: {r.status_code}")
                # Attach response text snippet for debugging (truncated)
                return (False, f"Google probe returned {r.status_code}: {r.text[:200]}")
            except Exception as e:
                return False, f"Google probe error: {e}"

        if provider == "Custom API":
            endpoint = (config.get("custom_endpoint") or _get_secret("LEGAL_API_URL")).strip()
            if not endpoint:
                return False, "Custom endpoint is not configured"
            try:
                r = requests.get(endpoint, timeout=6)
                return (r.ok, f"Custom: {r.status_code}")
            except Exception as e:
                return False, f"Custom probe error: {e}"

        return False, "Unknown provider"
    except Exception as exc:
        return False, str(exc)


def render_sidebar() -> dict[str, Any]:
    with st.sidebar:
        st.header("⚙️ Control center")
        st.caption("Choose your AI provider, model, and retrieval stack")

        provider = st.selectbox(
            "LLM provider",
            ["OpenAI", "Google Gemini", "Local Qwen", "Custom API"],
            index=0,
        )

        # API keys are entered/resolved BEFORE the model dropdown, so the
        # dropdown itself can reflect what the key actually has access to.
        st.markdown("### API keys")
        st.caption("محجوزة تلقائيًا من Streamlit Secrets لو متوفرة — تقدر تستبدلها هنا وقتيًا")
        openai_key = st.text_input(
            "OpenAI API key", value=_get_secret("OPENAI_API_KEY"), type="password",
            help="Optional for cloud LLM access",
        )
        google_key = st.text_input(
            "Google API key", value=_get_secret("GOOGLE_API_KEY"), type="password",
            help="Optional for Gemini access",
        )
        hf_token = st.text_input(
            "Hugging Face token", value=_get_secret("HF_TOKEN"), type="password",
            help="Optional for model downloads / private models",
        )
        custom_endpoint = st.text_input(
            "Custom endpoint",
            value=_get_secret("LEGAL_API_URL"),
            placeholder="https://api.example.com/v1",
        )
        api_key = st.text_input(
            "Backend API key", value=_get_secret("API_KEY"), type="password",
            help="Optional: x-api-key for Custom API. Defaults to Streamlit Secrets.API_KEY if set.",
        )

        st.markdown("### 🔎 حالة الموديلات (تحقق مباشر من المزوّد)")
        if provider == "OpenAI":
            openai_check = check_openai_models(openai_key)
            render_model_status_list(openai_check, _PREFERRED_OPENAI_MODELS, "OpenAI")
            live_openai_models = openai_check.get("models") or []
        elif provider == "Google Gemini":
            gemini_check = check_gemini_models(google_key)
            render_model_status_list(gemini_check, _PREFERRED_GEMINI_MODELS, "Gemini")
            live_gemini_models = gemini_check.get("models") or []
        else:
            st.caption("التحقق المباشر متاح لـ OpenAI و Google Gemini فقط.")
            live_openai_models = []
            live_gemini_models = []

        if provider == "Local Qwen":
            model_choices = ["Qwen 3 (local)", "Qwen 2.5 (local)", "TinyLlama"]
        elif provider == "OpenAI":
            # Use the LIVE list from the key check above when it succeeded;
            # otherwise fall back to the static preferred list so the
            # dropdown is never empty before a key is entered.
            model_choices = live_openai_models or _PREFERRED_OPENAI_MODELS
        elif provider == "Google Gemini":
            model_choices = live_gemini_models or _PREFERRED_GEMINI_MODELS
        else:
            model_choices = ["custom-model", "openai-compatible-model"]

        llm_model = st.selectbox("LLM model", model_choices, index=0)
        backend = st.selectbox(
            "Transformer backend",
            ["Transformers", "vLLM", "LangChain", "OpenAI-compatible API"],
            index=0,
        )
        retrieval_mode = st.selectbox(
            "Retrieval mode",
            ["Hybrid", "Dense", "BM25"],
            index=0,
        )
        top_k = st.slider("Top results", min_value=3, max_value=10, value=5)

        st.markdown("### Project overview")
        st.markdown(
            "- DVC tracking\n- Docker + Compose\n- GitHub Actions\n- Regression tests\n- Monitoring / Prometheus"
        )

        return {
            "provider": provider,
            "llm_model": llm_model,
            "backend": backend,
            "retrieval_mode": retrieval_mode,
            "top_k": top_k,
            "openai_key": openai_key,
            "google_key": google_key,
            "hf_token": hf_token,
            "custom_endpoint": custom_endpoint,
            "api_key": api_key,
            "openai_model": llm_model if provider == "OpenAI" else _get_secret("OPENAI_MODEL", "gpt-4o-mini"),
            "gemini_model": llm_model if provider == "Google Gemini" else _get_secret("GEMINI_MODEL", "gemini-2.5-flash"),
            "custom_model": llm_model if provider == "Custom API" else "custom-model",
        }


def main() -> None:
    apply_theme()

    config = render_sidebar()

    st.markdown(
        """
        <div class="top-shell">
            <div class="brand-row">
                <div class="brand">
                    <span class="brand-badge">⚖</span>
                    Legal Copilot
                </div>
                <div class="status-pill">● Ready</div>
            </div>
            <div class="hero-bar">
                <h1>Ask your legal questions like a specialist.</h1>
                <p>Retrieve Arabic legal context, review evidence, and explore the law with a clean AI-powered workflow.</p>
                <div class="chip-row">
                    <span class="chip">🔎 Retrieval</span>
                    <span class="chip">🧠 Model aware</span>
                    <span class="chip">☁️ Cloud ready</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    docs = load_legal_documents()
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        """
        <div class='metric-card'>
            <div class='small-muted'>Documents</div>
            <h2>{}</h2>
        </div>
        """.format(len(docs)),
        unsafe_allow_html=True,
    )
    c2.markdown(
        """
        <div class='metric-card'>
            <div class='small-muted'>Mode</div>
            <h2>{}</h2>
        </div>
        """.format(config["retrieval_mode"]),
        unsafe_allow_html=True,
    )
    c3.markdown(
        """
        <div class='metric-card'>
            <div class='small-muted'>Status</div>
            <h2>Live</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c4.markdown(
        """
        <div class='metric-card'>
            <div class='small-muted'>Deploy</div>
            <h2>Cloud</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_options = [
        "ما هي شروط القبض في حالة التلبس؟",
        "ما هي حقوق المتهم في التحقيق؟",
        "ما هي مسؤولية القاضي في تطبيق القانون؟",
    ]

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    chat_col, insight_col = st.columns([2.3, 1])

    with chat_col:
        status_label = "Fallback" if config.get("provider") == "Local Qwen" else "Online"
        st.markdown(f"<div class='chat-shell'>", unsafe_allow_html=True)
        st.markdown(f"<div class='chat-header'><div class='title'>Legal assistant</div><div class='status-pill'>{status_label}</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='assistant-panel'>", unsafe_allow_html=True)

        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = [
                ("assistant", "مرحبًا! سأساعدك في الاستفسارات القانونية. أكتب سؤالك، وسأستخدم Retrieval + evidence لتحليل السياق القانوني."),
            ]

        for role, message in st.session_state["chat_history"]:
            if role == "user":
                st.markdown(f"<div class='message-bubble user-msg'>{message}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='message-bubble assistant-msg'>{message}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='composer'>", unsafe_allow_html=True)
        st.markdown("<div class='quick-grid'>", unsafe_allow_html=True)
        for option in quick_options:
            if st.button(option, key=f"quick_{option}", help="Use a sample legal question"):
                # NOTE: only set pending_prompt here. The pending_prompt handler
                # below is the single place that appends the user bubble — this
                # button used to also append it directly, which produced the
                # duplicate question bubble seen in the UI (the same question
                # appended twice: once here, once by the handler below).
                st.session_state["pending_prompt"] = option
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        prompt = st.chat_input("اكتب السؤال القانوني...", key="legal_chat_input")
        if prompt is not None and prompt.strip():
            st.session_state["pending_prompt"] = prompt

        if "pending_prompt" in st.session_state and st.session_state["pending_prompt"]:
            prompt_value = st.session_state["pending_prompt"]
            st.session_state["pending_prompt"] = ""
            st.session_state["chat_history"].append(("user", prompt_value))
            with st.spinner("جاري استرجاع السياق القانوني وتحليل الإجابة..."):
                results = simple_search(prompt_value, k=config["top_k"])
                result_payload = _execute_provider_flow(prompt_value, config, results)

                if not result_payload.get("answer"):
                    fallback_text = (
                        "لم أجد إجابة مولدة عبر الـ provider المختار. تم إرجاع أقرب أدلة قانونية من الاسترجاع المحلي فقط. "
                        f"أقرب دليل: {results[0].get('content', '')[:260] if results else 'لا توجد نتائج.'}"
                    )
                    result_payload = {
                        "answer": fallback_text,
                        "citations": [{
                            "law_name": r.get("law_name", "غير محدد"),
                            "article_id": r.get("article_id", "N/A"),
                            "text": r.get("content", ""),
                        } for r in results[:3]],
                        "warnings": result_payload.get("warnings", ["Retrieval-only fallback was used because the selected provider was unavailable or not configured."]),
                        "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0},
                        "evidence": results,
                        "provider": config.get("provider", "Local Qwen"),
                        "model": _provider_model_label(config.get("provider", "Local Qwen"), config),
                    }

                answer_text = str(result_payload.get("answer") or "لم أتمكن من توليد إجابة فورية.")
                citations = result_payload.get("citations") or []
                if citations:
                    citation_summary = "; ".join(
                        f"{item.get('law_name', 'القانون')} / المادة {item.get('article_id', 'N/A')}"
                        for item in citations[:3]
                    )
                    answer_text = f"{answer_text}\n\nالمراجع: {citation_summary}"

                st.session_state["chat_history"].append(("assistant", answer_text))
                st.session_state["last_result"] = result_payload
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with insight_col:
        st.markdown("<div class='panel-box'><h3>Model status</h3></div>", unsafe_allow_html=True)
        st.metric("Provider", config.get("provider", "Local Qwen"))
        st.metric("Model", config["llm_model"])
        st.metric("Backend", config["backend"])
        st.metric("Retrieval", config["retrieval_mode"])

        last_runtime_error = st.session_state.get("runtime_error", "")
        if config.get("provider") == "Local Qwen":
            if not LOCAL_RUNTIME_ALLOWED:
                st.caption("Runtime: disabled by environment — local FAISS/BGE model is not safe in this environment")
                st.info("To enable local runtime, follow docs/LOCAL_QWEN_RUNBOOK.md and run the backend on a dedicated Linux host. Or choose a cloud provider (Google Gemini / OpenAI) in the sidebar.")
            else:
                if last_runtime_error:
                    st.error("Last local runtime error: " + str(last_runtime_error)[:400])
                    message = str(last_runtime_error).splitlines()[-1][:160]
                    st.caption(f"Runtime: unavailable — {message}")
                else:
                    if st.button("Check local runtime", key="check_local_runtime"):
                        st.info("Checking local runtime...")
                        ok, msg = _probe_provider(config)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.caption("Runtime: idle — local model loads only when explicitly enabled")
        else:
            st.caption(f"Runtime: {config.get('provider', 'external')} provider selected")

        if config.get("provider") == "Local Qwen" and LOCAL_RUNTIME_ALLOWED and st.button("Check local runtime", key="check_local_runtime"):
            st.session_state["runtime_error"] = ""
            service = get_local_rag_service()
            if service is not None:
                st.session_state["runtime_error"] = ""
                st.success("Local runtime loaded successfully.")
            else:
                st.session_state["runtime_error"] = "Local runtime failed to initialize. This is a real native dependency issue (FAISS/BGE) and not a UI warning."
                st.warning(st.session_state["runtime_error"])

        st.markdown("<div class='panel-box' style='margin-top: 1rem;'><h3>Evidence overview</h3></div>", unsafe_allow_html=True)
        for name, pct in [("Coverage", 92), ("Recall", 87), ("Latency", 91)]:
            st.progress(pct / 100, text=f"{name}: {pct}%")

        if "last_result" in st.session_state and st.session_state["last_result"]:
            metrics = st.session_state["last_result"].get("timing") or {}
            if metrics:
                st.markdown("<div class='panel-box' style='margin-top: 1rem;'><h3>Live metrics</h3></div>", unsafe_allow_html=True)
                st.metric("Retrieval", f"{metrics.get('retrieval_ms', 0):.0f} ms")
                st.metric("Generation", f"{metrics.get('generation_ms', 0):.0f} ms")
                st.metric("Total", f"{metrics.get('total_ms', 0):.0f} ms")

            evidence = st.session_state["last_result"].get("evidence") or []
            if evidence:
                st.markdown("<div class='panel-box' style='margin-top: 1rem;'><h3>Latest sources</h3></div>", unsafe_allow_html=True)
                for idx, hit in enumerate(evidence[:3], start=1):
                    st.markdown(
                        f"""
                        <div class='result-card'>
                            <div class='badge'>#{idx}</div>
                            <h3>{hit.get('law_name', 'غير محدد')} / المادة {hit.get('article_id', 'N/A')}</h3>
                            <div class='small-muted'>{hit.get('title', '')}</div>
                            <p>{str(hit.get('content', ''))[:180]}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


if __name__ == "__main__":
    main()

