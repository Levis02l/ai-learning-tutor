from anthropic import Anthropic

from app.config import settings
from app.llm.provider import LLMConfigurationError, LLMProviderError, LLMResponse


class ClaudeProvider:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise LLMConfigurationError(
                "ANTHROPIC_API_KEY is required for chat generation"
            )

        self._client = Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        try:
            response = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise LLMProviderError(f"Claude generation failed: {exc}") from exc

        text_parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if getattr(block, "type", None) == "text" and isinstance(text, str):
                text_parts.append(text)
        text = "\n".join(text_parts).strip()
        if not text:
            raise LLMProviderError("Claude returned an empty response")

        return LLMResponse(text=text)
