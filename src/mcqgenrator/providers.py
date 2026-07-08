import os
from functools import lru_cache

from mcqgenrator.logger import logger


class MissingAPIKeyError(Exception):
    """Raised when the selected provider's API key isn't configured."""


class ProviderUnavailableError(Exception):
    """Raised when the selected provider's package isn't installed."""


try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None


_PROVIDER_SPECS = {
    "Groq (Llama 3.3)": {
        "cls": lambda: ChatGroq,
        "env": "GROQ_API_KEY",
        "kwargs": lambda key: dict(groq_api_key=key, model_name="llama-3.3-70b-versatile", temperature=0.3),
    },
    "OpenAI (GPT-4o mini)": {
        "cls": lambda: ChatOpenAI,
        "env": "OPENAI_API_KEY",
        "kwargs": lambda key: dict(api_key=key, model="gpt-4o-mini", temperature=0.3),
    },
    "Anthropic (Claude Haiku)": {
        "cls": lambda: ChatAnthropic,
        "env": "ANTHROPIC_API_KEY",
        "kwargs": lambda key: dict(api_key=key, model="claude-haiku-4-5", temperature=0.3),
    },
}


def available_providers() -> list:
    """Providers whose LangChain integration package is installed (regardless of
    whether an API key is set yet -- the key is checked lazily at call time)."""
    return [name for name, spec in _PROVIDER_SPECS.items() if spec["cls"]() is not None]


@lru_cache(maxsize=8)
def get_llm(provider: str):
    spec = _PROVIDER_SPECS.get(provider)
    if spec is None:
        raise ProviderUnavailableError(f"Unknown provider: {provider}")

    cls = spec["cls"]()
    if cls is None:
        raise ProviderUnavailableError(
            f"The package for '{provider}' isn't installed. Add it to requirements.txt and pip install."
        )

    key = os.getenv(spec["env"])
    if not key:
        raise MissingAPIKeyError(
            f"{spec['env']} not found. Add it to your .env file to use {provider}."
        )

    logger.info("Initializing LLM provider: %s", provider)
    return cls(**spec["kwargs"](key))
