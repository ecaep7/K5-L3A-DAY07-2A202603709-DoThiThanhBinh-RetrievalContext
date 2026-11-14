"""Chạy agent thật trên một split với một hoặc nhiều cấu hình.

    python -m src.run_agent --split dev --configs A_dense B_lexical C_hybrid D_hybrid_multi E_hybrid_multi_nb
    python -m src.run_agent --split test --configs A_dense <cấu hình đã chọn>   (chỉ sau khi đã chốt trên dev)

Trace từng câu: results/agent/<config>_<split>.json. Tổng hợp: results/agent/summary_<split>.json.
"""
import argparse
import json

from .agent import ChunkOrder, run_agent
from .common import RESULTS, load_questions, write_json
from .configs import CONFIGS
from .eval_agent import evaluate_trace, summarize
from .llm import LLM
from .retrievers import DenseRetriever, HybridRetriever, LexicalRetriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--configs", nargs="+", required=True, choices=list(CONFIGS))
    args = parser.parse_args()

    questions = load_questions(args.split)
    by_id = {q["id"]: q for q in questions}
    llm = LLM()
    dense, lexical = DenseRetriever(), LexicalRetriever()
    retrievers = {"dense": dense, "lexical": lexical, "hybrid": HybridRetriever(dense, lexical)}
    order = ChunkOrder()

    summary_path = RESULTS / "agent" / f"summary_{args.split}.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    for name in args.configs:
        config = CONFIGS[name]
        traces = []
        for q in questions:
            trace = run_agent(q, llm, retrievers[config["method"]], config, order)
            trace["config_name"], trace["split"], trace["answerable"] = name, args.split, q["answerable"]
            if trace["status"] != "error":
                trace["eval"] = evaluate_trace(trace, q)
            traces.append(trace)
            mark = {"answered": "trả lời", "abstain": "từ chối", "error": "LỖI"}[trace["status"]]
            print(f"  {name} {q['id']}: {mark} | tìm {trace['searches']} lần | {trace['totals']['latency_s']} s"
                  + (f" | {trace['error']}" if trace["error"] else ""))
        write_json(RESULTS / "agent" / f"{name}_{args.split}.json", traces)
        summary[name] = {"config": config, "model": llm.model, "provider": llm.provider, **summarize(traces, by_id)}
        s = summary[name]
        print(f"{name}: tool use {s['tool_use']} | context evidence {s['context_evidence_rate']} | "
              f"từ chối đúng {s['abstained_unanswerable']} | từ chối nhầm {s['abstained_answerable']} | "
              f"lỗi {s['errors']} | {s['cost_usd']} USD | {s['avg_latency_s']} s/câu")
    write_json(summary_path, summary)
    print(f"Đã lưu {summary_path.relative_to(RESULTS.parent)}")


if __name__ == "__main__":
    main()
