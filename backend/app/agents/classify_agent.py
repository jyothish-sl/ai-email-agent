"""
Email Classification Agent (LangGraph)

Classifies a single email into one of the user's EmailClassification
categories. Primary path uses the user's configured LLM (structured output,
choosing from the category prompts). Falls back to keyword matching when no
LLM credential is configured, or the LLM call fails/errors.
"""

from __future__ import annotations

import re
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.services.llm import LLMNotConfigured, build_chat_model


# ============================================================================
# Data Shapes
# ============================================================================


class ClassificationOption(TypedDict):
    """A single user-defined category available for classification."""

    id: str
    name: str
    prompt: str
    keywords: list[str]


class ClassifyState(TypedDict, total=False):
    """State threaded through the classification graph for one email."""

    # Inputs
    subject: str
    snippet: str
    body_text: Optional[str]
    sender: str
    categories: list[ClassificationOption]
    llm_credential: Optional[dict]  # decrypted {"provider": ..., "api_key": ..., "model": ...}

    # Outputs
    classification_id: Optional[str]
    classification_name: Optional[str]
    classification_confidence: Optional[float]
    classification_method: Optional[str]  # "llm" | "keyword" | "none"
    error: Optional[str]

    # Populated only when the LLM node actually made a call (not on the
    # keyword-fallback path). {"input_tokens": int, "output_tokens": int,
    # "total_tokens": int, "model": str} - any of the token fields may be
    # None if the provider didn't report usage.
    token_usage: Optional[dict]


class _LLMVerdict(BaseModel):
    """Structured output schema requested from the LLM."""

    category_name: Optional[str] = Field(
        default=None,
        description=(
            "The single best-matching category name from the provided list, "
            "or null if none of the categories genuinely apply."
        ),
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the chosen category, 0.0-1.0. 0 if category_name is null.",
    )
    reasoning: str = Field(default="", description="One short sentence explaining the choice.")


# ============================================================================
# Nodes
# ============================================================================


def _keyword_hit(keyword: str, haystack: str) -> bool:
    """
    Whole-word/phrase match for a single keyword against the haystack.

    Plain substring matching (`kw in haystack`) false-positives constantly -
    e.g. the "Newsletter" keyword "read" matches inside "already" or
    "readjust", and "job" matches inside "adjoin". \\b word boundaries
    keep this to genuine word/phrase occurrences while still allowing
    multi-word keywords like "application status".
    """
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, haystack) is not None


def _keyword_classify(state: ClassifyState) -> ClassifyState:
    """
    Fallback classifier: scores each category by counting keyword hits in
    subject + snippet + body_text. Used when no LLM credential is
    configured, or the LLM node errors out.
    """
    haystack = " ".join(
        filter(None, [state.get("subject", ""), state.get("snippet", ""), state.get("body_text") or ""])
    ).lower()

    best_id = None
    best_name = None
    best_hits = 0

    for cat in state.get("categories", []):
        keywords = cat.get("keywords") or []
        hits = sum(1 for kw in keywords if kw and _keyword_hit(kw, haystack))
        if hits > best_hits:
            best_hits = hits
            best_id = cat["id"]
            best_name = cat["name"]

    if best_hits == 0:
        return {
            **state,
            "classification_id": None,
            "classification_name": None,
            "classification_confidence": 0.0,
            "classification_method": "none",
        }

    # More keyword hits -> higher confidence, capped at 0.75. Keyword
    # matching is never as trustworthy as an LLM read, so it never reports
    # near-certainty.
    confidence = min(0.75, 0.35 + 0.1 * best_hits)

    return {
        **state,
        "classification_id": best_id,
        "classification_name": best_name,
        "classification_confidence": confidence,
        "classification_method": "keyword",
    }


def _llm_classify(state: ClassifyState) -> ClassifyState:
    """
    Primary classifier: asks the user's configured LLM to pick the single
    best-matching category (or none) from the user-defined categories,
    using each category's `prompt` as the description of what belongs there.
    """
    credential = state.get("llm_credential")
    categories = state.get("categories", [])

    if not credential or not categories:
        return {**state, "error": "no_llm_credential_or_categories"}

    try:
        model = build_chat_model(credential)
    except LLMNotConfigured as exc:
        return {**state, "error": f"llm_unavailable: {exc}"}

    category_list = "\n".join(f"- {c['name']}: {c['prompt']}" for c in categories)

    system_prompt = (
        "You are an email triage assistant. Given an email and a list of "
        "user-defined categories, choose the single category that best "
        "matches the email's content and intent. Only choose a category if "
        "it genuinely applies — if none of the categories fit well, return "
        "null for category_name rather than forcing a weak match."
    )

    user_prompt = (
        f"Categories:\n{category_list}\n\n"
        f"Email:\n"
        f"From: {state.get('sender', '')}\n"
        f"Subject: {state.get('subject', '')}\n"
        f"Body:\n{(state.get('body_text') or state.get('snippet') or '')[:4000]}"
    )

    try:
        # include_raw=True gives back {"raw": AIMessage, "parsed": ..., "parsing_error": ...}
        # instead of just the parsed object, so we can still read token usage
        # off the raw message even though we only care about the structured
        # result for classification itself.
        structured_model = model.with_structured_output(_LLMVerdict, include_raw=True)
        response = structured_model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:  # noqa: BLE001 - any LLM/network failure falls back to keywords
        return {**state, "error": f"llm_call_failed: {exc}"}

    raw_message = response.get("raw")
    verdict: Optional[_LLMVerdict] = response.get("parsed")

    if response.get("parsing_error") or verdict is None:
        return {**state, "error": f"llm_parse_failed: {response.get('parsing_error')}"}

    # usage_metadata is a standardized attribute LangChain attaches to the
    # raw AIMessage (input_tokens/output_tokens/total_tokens). Not every
    # provider/version populates it (some local Ollama models don't), so
    # everything here is best-effort and may come back None.
    usage = getattr(raw_message, "usage_metadata", None) or {}
    token_usage = {
        "model": getattr(raw_message, "response_metadata", {}).get("model") or credential.get("model"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }

    if not verdict.category_name:
        return {
            **state,
            "classification_id": None,
            "classification_name": None,
            "classification_confidence": 0.0,
            "classification_method": "llm",
            "token_usage": token_usage,
        }

    # Map the returned name back to its category id (LLM only sees names)
    matched = next(
        (c for c in categories if c["name"].strip().lower() == verdict.category_name.strip().lower()),
        None,
    )
    if not matched:
        # LLM hallucinated a name outside the provided list - treat as no match.
        # Still record token_usage: the call was made and billed/consumed
        # even though we're falling back to keyword matching for the result.
        return {
            **state,
            "classification_id": None,
            "classification_name": None,
            "classification_confidence": 0.0,
            "classification_method": "llm",
            "error": "llm_returned_unknown_category",
            "token_usage": token_usage,
        }

    return {
        **state,
        "classification_id": matched["id"],
        "classification_name": matched["name"],
        "classification_confidence": verdict.confidence,
        "classification_method": "llm",
        "token_usage": token_usage,
    }


def _route_after_llm(state: ClassifyState) -> str:
    """If the LLM node hit an error, fall back to keyword matching."""
    return "keyword_classify" if state.get("error") else END


# ============================================================================
# Graph
# ============================================================================


def _build_graph():
    graph = StateGraph(ClassifyState)
    graph.add_node("llm_classify", _llm_classify)
    graph.add_node("keyword_classify", _keyword_classify)

    graph.add_edge(START, "llm_classify")
    graph.add_conditional_edges(
        "llm_classify",
        _route_after_llm,
        {"keyword_classify": "keyword_classify", END: END},
    )
    graph.add_edge("keyword_classify", END)

    return graph.compile()


classify_graph = _build_graph()
