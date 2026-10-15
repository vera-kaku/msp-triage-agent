"""Create a chat model from a provider name and environment variables."""

from __future__ import annotations

import os

from ..config import Config
from .base import ChatModel

PROVIDERS = ("keyword", "deepseek", "openai", "azure", "anthropic")


def _require(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        raise SystemExit(f"Set {var} to use this provider (see .env.example).")
    return value


def make_model(provider: str, config: Config, model: str | None = None) -> ChatModel:
    model = model or os.environ.get("TRIAGE_MODEL")

    if provider == "keyword":
        from .keyword_model import KeywordModel
        return KeywordModel(config)

    if provider == "anthropic":
        import anthropic

        from .anthropic_model import AnthropicModel
        client = anthropic.Anthropic(api_key=_require("ANTHROPIC_API_KEY"))
        return AnthropicModel(client, model or "claude-haiku-5-5")

    from .openai_compat import OpenAICompatibleModel

    if provider == "deepseek":
        from openai import OpenAI
        client = OpenAI(api_key=_require("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        name = model or "deepseek-flash"
        thinking = os.environ.get("TRIAGE_THINKING", "disabled")
        return OpenAICompatibleModel(client, name, f"deepseek/{name}/thinking-{thinking}",
                                     extra_body={"thinking": {"type": thinking}})

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=_require("OPENAI_API_KEY"))
        if not model:
            raise SystemExit("Set TRIAGE_MODEL or pass --model to choose an OpenAI model.")
        return OpenAICompatibleModel(client, model, f"openai/{model}")

    if provider == "azure":
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=_require("AZURE_OPENAI_API_KEY"),
            azure_endpoint=_require("AZURE_OPENAI_ENDPOINT"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
        if not model:
            raise SystemExit("Set TRIAGE_MODEL to your Azure OpenAI deployment name.")
        return OpenAICompatibleModel(client, model, f"azure/{model}")

    raise SystemExit(f"Unknown provider {provider!r}. Choose from: {', '.join(PROVIDERS)}")
