from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, focus_topic: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._focus_topic = focus_topic

    @property
    def model(self) -> str:
        return self._model

    def _build_system_prompt(self, focus_topic: str) -> str:
        return (
            "Ты — крайне строгий и эмоциональный технический ментор. "
            f"Твоя единственная цель — чтобы пользователь изучал только {focus_topic}. "
            "Твои правила: "
            f"Если контент касается {focus_topic}: "
            "Хвали пользователя за продуктивность и верный выбор материала. "
            "Сделай ОЧЕНЬ ПОДРОБНЫЙ, глубокий и структурированный суммарайз "
            "предоставленного контента. "
            "Используй воодушевляющий и поддерживающий тон. "
            f"Если контент НЕ касается {focus_topic}: "
            "Сначала дай максимально КРАТКИЙ пересказ (не более 1-2 предложений), "
            "чтобы пользователь просто понял суть. "
            "Сразу после этого перейди на холодный, суровый и осуждающий тон. "
            "Прямо заяви, что пользователь тратит время на ерунду, позорится и немедленно обязан "
            f"вернуться к изучению {focus_topic}. "
            "Важно: Всегда оставайся в роли. Твой ответ должен быть либо наградой "
            "за фокус на теме, "
            "либо жестким выговором за отвлечение."
        )

    async def generate(self, prompt: str, focus_topic: str | None = None) -> str:
        resolved_focus_topic = focus_topic or self._focus_topic

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "system": self._build_system_prompt(resolved_focus_topic),
                    "stream": False,
                },
            )
            response.raise_for_status()

        payload = response.json()
        return str(payload.get("response", ""))
