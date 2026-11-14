"""Chỉ số tự động cho các lượt chạy agent. Chỉ đếm và đối chiếu, không chấm nội dung câu trả lời
(phần đó chấm tay theo BENCHMARK.md).

- tool_use          : số lượt có gọi search / số lượt chạy không lỗi
- first-search Hit  : Hit@1, Evidence Hit@3 của lần tìm đầu tiên (câu tìm do model đặt)
- Context Evidence Rate: số câu có đáp án mà context cuối chứa trọn evidence / số câu có đáp án
- citation_in_context: số trích dẫn có id nằm trong context / tổng trích dẫn (chưa phải "hỗ trợ đúng")
- abstention        : câu thiếu bằng chứng bị từ chối / tổng; câu có đáp án bị từ chối nhầm / tổng
"""
import json
from collections import Counter

from .common import DATA
from .eval_retrieval import is_hit

CHUNKS = {c["id"]: c for c in json.loads((DATA / "chunks.json").read_text(encoding="utf-8"))}


def evaluate_trace(trace: dict, question: dict) -> dict:
    out = {"status": trace["status"], "searches": trace["searches"],
           "citations": len(trace["citations"]), "citations_in_context": len(trace["citations"]) - len(trace["citations_not_in_context"])}
    if question["answerable"]:
        first = next((e for e in trace["events"] if e["type"] == "search"), None)
        first_hits = [is_hit(CHUNKS[r["id"]], question) for r in (first["results"] if first else [])]
        out["first_hit1"] = bool(first_hits[:1] and first_hits[0])
        out["first_hit3"] = any(first_hits[:3])
        out["context_has_evidence"] = any(is_hit(c, question) for c in trace["context"])
    return out


def summarize(traces: list[dict], questions: dict[str, dict]) -> dict:
    ok = [t for t in traces if t["status"] != "error"]
    ans = [t for t in ok if questions[t["query_id"]]["answerable"]]
    unans = [t for t in ok if not questions[t["query_id"]]["answerable"]]
    answered = [t for t in ok if t["status"] == "answered"]
    ev = {t["query_id"]: t["eval"] for t in ok}
    n_cit = sum(ev[t["query_id"]]["citations"] for t in ok)

    def frac(n: int, d: int) -> str:
        return f"{n}/{d}" + (f" ({n / d:.0%})" if d else " (không áp dụng)")

    return {
        "runs": len(traces), "errors": len(traces) - len(ok),
        "tool_use": frac(sum(t["searches"] > 0 for t in ok), len(ok)),
        "searches_per_question": dict(sorted(Counter(t["searches"] for t in ok).items())),
        "first_search_hit1": frac(sum(ev[t["query_id"]]["first_hit1"] for t in ans), len(ans)),
        "first_search_hit3": frac(sum(ev[t["query_id"]]["first_hit3"] for t in ans), len(ans)),
        "context_evidence_rate": frac(sum(ev[t["query_id"]]["context_has_evidence"] for t in ans), len(ans)),
        "citations_in_context": frac(sum(ev[t["query_id"]]["citations_in_context"] for t in ok), n_cit),
        "answers_with_citation": frac(sum(ev[t["query_id"]]["citations"] > 0 for t in answered), len(answered)),
        "abstained_unanswerable": frac(sum(t["status"] == "abstain" for t in unans), len(unans)),
        "abstained_answerable": frac(sum(t["status"] == "abstain" for t in ans), len(ans)),
        "avg_context_chars": round(sum(t["context_chars"] for t in ok) / len(ok)) if ok else 0,
        "llm_calls": sum(t["totals"]["llm_calls"] for t in traces),
        "prompt_tokens": sum(t["totals"]["prompt_tokens"] for t in traces),
        "completion_tokens": sum(t["totals"]["completion_tokens"] for t in traces),
        "cost_usd": round(sum(t["totals"]["cost_usd"] for t in traces), 5),
        "avg_latency_s": round(sum(t["totals"]["latency_s"] for t in traces) / len(traces), 2) if traces else 0,
    }
