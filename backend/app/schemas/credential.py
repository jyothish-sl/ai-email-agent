from typing import Literal
from pydantic import BaseModel, Field, field_validator

Category = Literal["llm", "email"]

PROVIDERS: dict[str, dict] = {
    "openai": {
        "category": "llm",
        "display_name": "OpenAI",
        "fields": [{"name": "api_key", "kind": "secret", "required": True}],
    },
    "anthropic": {
        "category": "llm",
        "display_name": "Anthropic",
        "fields": [{"name": "api_key", "kind": "secret", "required": True}],
    },
    "google": {
        "category": "llm",
        "display_name": "Google Gemini",
        "fields": [{"name": "api_key", "kind": "secret", "required": True}],
    },
    "azure_openai": {
        "category": "llm",
        "display_name": "Azure OpenAI",
        "fields": [
            {"name": "api_key", "kind": "secret", "required": True},
            {"name": "endpoint", "kind": "text", "required": True},
            {"name": "deployment", "kind": "text", "required": True},
        ],
    },
    "mistral": {
        "category": "llm",
        "display_name": "Mistral",
        "fields": [{"name": "api_key", "kind": "secret", "required": True}],
    },
    "cohere": {
        "category": "llm",
        "display_name": "Cohere",
        "fields": [{"name": "api_key", "kind": "secret", "required": True}],
    },
    "custom_llm": {
        "category": "llm",
        "display_name": "Custom / OpenAI-compatible",
        "fields": [
            {"name": "base_url", "kind": "text", "required": True},
            {"name": "api_key", "kind": "secret", "required": False},
        ],
    },
    "ollama": {
        "category": "llm",
        "display_name": "Ollama",
        "fields": [
            {"name": "base_url", "kind": "text", "required": False},
        ],
    },
    "gmail": {
        "category": "email",
        "display_name": "Gmail",
        "fields": [
            {"name": "email", "kind": "text", "required": True},
            {"name": "app_password", "kind": "secret", "required": True},
        ],
    },
    "outlook": {
        "category": "email",
        "display_name": "Outlook / Office 365",
        "fields": [
            {"name": "email", "kind": "text", "required": True},
            {"name": "app_password", "kind": "secret", "required": True},
        ],
    },
    "smtp": {
        "category": "email",
        "display_name": "Custom SMTP",
        "fields": [
            {"name": "host", "kind": "text", "required": True},
            {"name": "port", "kind": "text", "required": True},
            {"name": "username", "kind": "text", "required": True},
            {"name": "password", "kind": "secret", "required": True},
            {"name": "use_tls", "kind": "text", "required": False},
        ],
    },
    "imap": {
        "category": "email",
        "display_name": "Custom IMAP",
        "fields": [
            {"name": "host", "kind": "text", "required": True},
            {"name": "port", "kind": "text", "required": True},
            {"name": "username", "kind": "text", "required": True},
            {"name": "password", "kind": "secret", "required": True},
            {"name": "use_ssl", "kind": "text", "required": False},
        ],
    },
}


def mask_secret_field(value: str) -> str:
    value = str(value)
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def build_masked_preview(provider: str, secret: dict) -> dict:
    spec = PROVIDERS[provider]
    preview = {}
    for field in spec["fields"]:
        name = field["name"]
        if name not in secret or secret[name] in (None, ""):
            continue
        preview[name] = (
            mask_secret_field(secret[name]) if field["kind"] == "secret" else secret[name]
        )
    return preview


class CredentialCreate(BaseModel):
    category: Category
    provider: str
    model_name: str | None = None
    label: str = Field(min_length=1, max_length=100)
    secret: dict[str, str] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def provider_must_be_known(cls, v: str) -> str:
        if v not in PROVIDERS:
            raise ValueError(f"Unknown provider '{v}'")
        return v

    def validate_against_category(self) -> None:
        spec = PROVIDERS[self.provider]
        if spec["category"] != self.category:
            raise ValueError(
                f"Provider '{self.provider}' belongs to category '{spec['category']}', not '{self.category}'"
            )

        if self.provider in {"openai", "ollama"} and not self.model_name:
            raise ValueError(f"Model name is required for provider '{self.provider}'")

        missing = [
            f["name"]
            for f in spec["fields"]
            if f["required"] and not self.secret.get(f["name"])
        ]
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")


class CredentialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    model_name: str | None = None
    secret: dict[str, str] | None = None


class CredentialOut(BaseModel):
    id: str
    category: Category
    provider: str
    provider_display_name: str
    model_name: str | None = None
    label: str
    is_active: bool
    masked_preview: dict
    created_at: str
    updated_at: str


class ProviderField(BaseModel):
    name: str
    kind: Literal["secret", "text"]
    required: bool


class ProviderInfo(BaseModel):
    provider: str
    category: Category
    display_name: str
    fields: list[ProviderField]