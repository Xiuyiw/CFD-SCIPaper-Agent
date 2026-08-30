"""Dependency-free AI provider configuration and placeholder interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class ProviderUnavailable(RuntimeError):
    """Raised only when generation is requested without a usable provider."""


class AIProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    @property
    def available(self) -> bool: ...

    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None = None
    model: str | None = None
    endpoint: str | None = None

    @classmethod
    def from_env(cls, name: str) -> ProviderConfig:
        prefix = name.upper().replace("-", "_")
        return cls(
            name=name,
            api_key=os.getenv(f"{prefix}_API_KEY"),
            model=os.getenv(f"{prefix}_MODEL"),
            endpoint=os.getenv(f"{prefix}_ENDPOINT"),
        )


class ConfiguredProvider:
    """Configuration placeholder; SDK/network integration is intentionally deferred."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.name = config.name

    @property
    def configured(self) -> bool:
        if self.name == "local":
            return bool(self.config.endpoint)
        return bool(self.config.api_key)

    @property
    def available(self) -> bool:
        return False

    def generate(self, prompt: str) -> str:
        if not self.configured:
            requirement = "endpoint" if self.name == "local" else "API key"
            raise ProviderUnavailable(f"{self.name} provider has no configured {requirement}")
        raise ProviderUnavailable(
            f"{self.name} transport is a configuration placeholder in this milestone"
        )


class OpenAIProvider(ConfiguredProvider):
    pass


class DeepSeekProvider(ConfiguredProvider):
    pass


class GeminiProvider(ConfiguredProvider):
    pass


class ClaudeProvider(ConfiguredProvider):
    pass


class LocalProvider(ConfiguredProvider):
    pass


PROVIDER_TYPES: dict[str, type[ConfiguredProvider]] = {
    "openai": OpenAIProvider,
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "local": LocalProvider,
}


def create_provider(config: ProviderConfig) -> AIProvider:
    normalized = config.name.casefold()
    if normalized not in PROVIDER_TYPES:
        raise ValueError(f"unsupported AI provider: {config.name}")
    if normalized != config.name:
        config = ProviderConfig(
            name=normalized,
            api_key=config.api_key,
            model=config.model,
            endpoint=config.endpoint,
        )
    return PROVIDER_TYPES[normalized](config)
