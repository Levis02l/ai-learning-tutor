from dataclasses import dataclass
from typing import Protocol


class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    text: str


class LLMProvider(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        pass
