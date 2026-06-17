from openai import OpenAI

from app.config import settings
from app.llm.provider import LLMConfigurationError, LLMProviderError, LLMResponse


class OpenAIProvider:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is required for chat generation"
            )

        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        try:
            response = self._client.responses.create(
                model=settings.openai_chat_model,
                instructions=system_prompt,
                input=user_prompt,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise LLMProviderError(f"OpenAI generation failed: {exc}") from exc

        text = getattr(response, "output_text", "").strip()
        if not text:
            raise LLMProviderError("OpenAI returned an empty response")

        return LLMResponse(text=text)
