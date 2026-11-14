"""Kiểm tra kết nối model (Claude API hoặc OpenRouter) và khả năng gọi công cụ (tool calling) của model.

    python scripts/check_llm.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.llm import LLM  # noqa: E402

TOOL = [{"type": "function", "function": {
    "name": "search_documents",
    "description": "Search the management textbook for passages relevant to a query.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]

llm = LLM()
message, usage = llm.chat(
    [{"role": "user", "content": "Use the search tool to look up what heuristics are. Do not answer yet."}],
    tools=TOOL)
calls = message.tool_calls or []
print(f"Nhà cung cấp: {usage['provider']} | Model: {usage['model']}")
print(f"Gọi công cụ: {'CÓ' if calls else 'KHÔNG'}"
      + (f" -> {calls[0].function.name}({json.loads(calls[0].function.arguments)})" if calls else ""))
print(f"Token: {usage['prompt_tokens']} vào / {usage['completion_tokens']} ra | "
      f"chi phí {usage['cost_usd']:.6f} USD ({usage['cost_source']}) | {usage['latency_s']} giây")
