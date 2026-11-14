"""Gọi model AI qua API tương thích OpenAI. Ghi lại token, chi phí và thời gian của mỗi lượt gọi.

Chọn nhà cung cấp trong .env bằng LLM_PROVIDER:
- anthropic  : Claude API (key ANTHROPIC_API_KEY), dùng lớp tương thích OpenAI SDK của Anthropic.
- openrouter : OpenRouter (key OPENROUTER_API_KEY).
"""
import os
import time

from openai import BadRequestError, OpenAI

from .common import ROOT  # noqa: F401  (nạp .env)

PROVIDERS = {
    # base_url, biến chứa key, model mặc định, giá USD / 1 triệu token (vào, ra)
    "anthropic": ("https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY", "claude-haiku-5-5", 0.10, 0.50),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openai/gpt-4.1-mini", 0.40, 1.60),
}


class LLM:
    def __init__(self, model: str | None = None, temperature: float | None = 0.0) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
        if self.provider not in PROVIDERS:
            raise SystemExit(f"LLM_PROVIDER phải là một trong {list(PROVIDERS)}")
        base_url, key_name, default_model, price_in, price_out = PROVIDERS[self.provider]
        key = os.getenv(key_name, "").strip()
        if not key:
            raise SystemExit(f"Thiếu {key_name} trong .env")
        self.model = model or os.getenv("LLM_MODEL") or default_model
        # Giá dùng để tính chi phí; có thể ghi đè trong .env nếu bảng giá thay đổi.
        self.price_in = float(os.getenv("LLM_PRICE_IN_PER_M", price_in))
        self.price_out = float(os.getenv("LLM_PRICE_OUT_PER_M", price_out))
        self.temperature = temperature
        self.client = OpenAI(base_url=base_url, api_key=key, timeout=90, max_retries=2)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024):
        """Trả về (message, usage). usage gồm prompt_tokens, completion_tokens, cost_usd, latency_s."""
        kwargs = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if tools:
            kwargs["tools"], kwargs["tool_choice"] = tools, "auto"
        if self.provider == "openrouter":
            kwargs["extra_body"] = {"usage": {"include": True}}   # yêu cầu OpenRouter trả chi phí thực
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            if "temperature" not in str(exc).lower() or "temperature" not in kwargs:
                raise
            # Một số model không nhận temperature: gọi lại không có tham số này và ghi nhớ.
            self.temperature = None
            kwargs.pop("temperature")
            response = self.client.chat.completions.create(**kwargs)
        latency = time.perf_counter() - started
        u = response.usage
        prompt, completion = (u.prompt_tokens, u.completion_tokens) if u is not None else (0, 0)
        reported = getattr(u, "cost", None) if u is not None else None
        usage = {"prompt_tokens": prompt, "completion_tokens": completion,
                 "cost_usd": float(reported) if reported is not None
                 else (prompt * self.price_in + completion * self.price_out) / 1e6,
                 "cost_source": "nhà cung cấp trả về" if reported is not None
                 else f"tính theo giá {self.price_in}/{self.price_out} USD mỗi 1M token",
                 "latency_s": round(latency, 3), "model": getattr(response, "model", None) or self.model,
                 "provider": self.provider}
        return response.choices[0].message, usage
