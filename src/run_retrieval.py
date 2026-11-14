"""So sánh các phương pháp truy xuất (chưa dùng LLM).

    python -m src.run_retrieval --split dev
    python -m src.run_retrieval --split dev --methods dense lexical hybrid --top-k 10

Query = nguyên văn câu hỏi; filter = phạm vi người dùng nêu (trường `filter`), không bao giờ dùng gold.
Ghi trace từng câu vào results/retrieval/<method>_<split>.json và bảng tổng hợp summary_<split>.json.
"""
import argparse
import time

from .common import RESULTS, load_questions, write_json
from .eval_retrieval import score_query, summarize
from .retrievers import DenseRetriever, HybridRetriever, LexicalRetriever


def build(methods: list[str]) -> dict:
    dense = DenseRetriever() if {"dense", "hybrid"} & set(methods) else None
    lexical = LexicalRetriever() if {"lexical", "hybrid"} & set(methods) else None
    available = {"dense": dense, "lexical": lexical,
                 "hybrid": HybridRetriever(dense, lexical) if dense and lexical else None}
    return {m: available[m] for m in methods}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--methods", nargs="+", default=["dense", "lexical", "hybrid"],
                        choices=["dense", "lexical", "hybrid"])
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    questions = load_questions(args.split)
    retrievers = build(args.methods)
    summary = {}
    for name, retriever in retrievers.items():
        traces, scored, started = [], [], time.perf_counter()
        for q in questions:
            t0 = time.perf_counter()
            try:
                results, error = retriever.search(q["question"], args.top_k, q.get("filter")), None
            except Exception as exc:   # ghi lỗi, không thay bằng kết quả giả
                results, error = [], f"{type(exc).__name__}: {exc}"
            trace = {"query_id": q["id"], "answerable": q["answerable"], "query": q["question"],
                     "filter": q.get("filter"), "method": name, "top_k": args.top_k,
                     "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "error": error,
                     "results": [{k: r[k] for k in ("rank", "id", "score", "source_id", "source", "page", "chapter", "text")}
                                 | ({"from": r["from"]} if "from" in r else {}) for r in results]}
            if q["answerable"]:
                trace["eval"] = score_query(q, results)
                scored.append(trace["eval"])
            traces.append(trace)
        s = summarize(scored)
        s["errors"] = sum(t["error"] is not None for t in traces)
        s["seconds_total"] = round(time.perf_counter() - started, 2)
        s["ms_per_query"] = round(1000 * s["seconds_total"] / len(questions), 1)
        summary[name] = s
        write_json(RESULTS / "retrieval" / f"{name}_{args.split}.json", traces)

    write_json(RESULTS / "retrieval" / f"summary_{args.split}.json",
               {"split": args.split, "top_k": args.top_k, "query": "nguyên văn câu hỏi", "filter": "trường filter của câu hỏi",
                "methods": summary})
    print(f"Tập {args.split} - {summary[next(iter(summary))]['N']} câu có đáp án (câu thiếu bằng chứng không tính):")
    for name, s in summary.items():
        print(f"  {name:8s} Hit@1 {s['hit1']}/{s['N']} | Evidence Hit@3 {s['hit3']}/{s['N']} | "
              f"Recall@10 {s['hit10']}/{s['N']} | MRR@10 {s['mrr10']} | {s['ms_per_query']} ms/câu | lỗi {s['errors']}")
    print(f"Trace: results/retrieval/<method>_{args.split}.json")


if __name__ == "__main__":
    main()
