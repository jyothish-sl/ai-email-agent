"""
LLM Credential Helper

Decrypts a user's "llm" category Credential and builds a LangChain chat
model instance from it, so agents (e.g. the classification agent) can call
whichever provider/model the user configured — mirrors the pattern used by
app.services.mailbox.imap_config_from_credential for email credentials.
"""

from __future__ import annotations

import json

# core.security.decrypt_data takes/returns a plain string (it's a thin
# Fernet wrapper), so the encrypted_secret column holds a Fernet-encrypted
# JSON string. We decrypt then json.loads it here.
from app.core.security import decrypt_data

from app.models.credential import Credential

# Providers that need an api_key. Ollama runs locally/self-hosted and
# doesn't require one.
_PROVIDERS_REQUIRING_API_KEY = {"anthropic", "openai", "gemini"}


class LLMNotConfigured(Exception):
    """Raised when a usable LLM credential can't be built (missing/invalid/unsupported)."""


def decrypt_llm_credential(credential: Credential) -> dict:
    """
    Decrypt an "llm" category Credential into its secret fields.

    encrypted_secret holds a Fernet-encrypted JSON string of provider
    secrets (api_key, base_url, etc. — whatever that provider's field spec
    defines). The model itself is NOT part of the secret blob — it's the
    Credential.model_name column, set directly at credential-creation time
    (see CredentialModal / POST /credentials) — so it's merged in here
    from the row, not from the decrypted JSON.

    Args:
        credential: Credential ORM object with category == "llm"

    Returns:
        Decrypted secret dict, with "provider" and "model" merged in from
        the credential row (model may be None if the provider/UI didn't
        set one, e.g. anthropic/gemini currently have no model picker)

    Raises:
        LLMNotConfigured: If the credential isn't an LLM credential, or the
            stored secret can't be decrypted/parsed
    """
    if credential.category != "llm":
        raise LLMNotConfigured("Credential is not an LLM credential")

    raw = decrypt_data(credential.encrypted_secret)
    if raw is None:
        raise LLMNotConfigured("LLM credential has no stored secret")

    try:
        secret = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise LLMNotConfigured("LLM credential secret is not valid JSON") from exc

    secret["provider"] = credential.provider
    secret["model"] = credential.model_name  # authoritative source, not the JSON blob
    return secret


def build_chat_model(secret: dict):
    """
    Build a LangChain chat model from a decrypted LLM credential secret dict.

    Args:
        secret: dict containing at least "provider"
            ("anthropic" | "openai" | "ollama"). Cloud providers also need
            "api_key". May also contain "model" (falls back to a sane
            per-provider default) and "base_url" (for OpenAI-compatible
            proxies, or a non-default Ollama host).

    Returns:
        A LangChain BaseChatModel instance, ready for .invoke() or
        .with_structured_output(...).

    Raises:
        LLMNotConfigured: If a required field is missing or provider is unsupported
    """
    provider = (secret.get("provider") or "").lower()

    if provider in _PROVIDERS_REQUIRING_API_KEY and not secret.get("api_key"):
        raise LLMNotConfigured(f"LLM credential is missing an api_key for provider {provider!r}")

    # Without an explicit timeout, a stuck/unreachable model (most commonly a
    # local Ollama instance that isn't running, or an unresolvable
    # base_url) hangs the request indefinitely with no error and no log
    # output - which just looks like the endpoint "loading forever" from the
    # caller's side. Bounding it here means a bad connection surfaces as a
    # normal llm_call_failed error within a fixed time instead.
    request_timeout_seconds = 60

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=secret.get("model") or "claude-sonnet-4-6",
            api_key=secret["api_key"],
            temperature=0,
            default_request_timeout=request_timeout_seconds,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=secret.get("model") or "gpt-4o-mini",
            api_key=secret["api_key"],
            base_url=secret.get("base_url"),
            temperature=0,
            request_timeout=request_timeout_seconds,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=secret.get("model") or "phi3:mini",
            base_url=secret.get("base_url") or "http://host.docker.internal:11434",
            temperature=0,
            client_kwargs={"timeout": request_timeout_seconds},
        )

    raise LLMNotConfigured(f"Unsupported LLM provider: {provider!r}")
