"""Tổng hợp nhãn chấm tay trên test bằng script của đề bài (starter/agent_metrics.py).

    python scripts/summarize_reviews.py

Đọc results/review/test_review.csv, chuyển thành cases/traces/reviews theo định dạng starter, gọi
starter.agent_metrics.aggregate cho từng cấu hình, cộng thêm phân bố điểm context.
Kết quả: results/review/summary_test.json và các file *_cases/traces/reviews.json để đối chiếu.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "starter"))
from agent_metrics import aggregate  # noqa: E402

from src.common import load_questions, write_json  # noqa: E402

REVIEW = ROOT / "results" / "review"


def main() -> None:
    with open(REVIEW / "test_review.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cases = [{"id": q["id"], "split": q["split"], "answerable": q["answerable"]} for q in load_questions("test")]
    report = {}
    for config in dict.fromkeys(r["config"] for r in rows):
        mine = [r for r in rows if r["config"] == config]
        traces_raw = {t["query_id"]: t for t in
                      json.loads((ROOT / "results" / "agent" / f"{config}_test.json").read_text(encoding="utf-8"))}
        traces, reviews = [], []
        for r in mine:
            t = traces_raw[r["query_id"]]
            # Starter đếm tool use qua event có khóa "event" == "search": chuẩn hóa sang định dạng đó.
            events = [{"event": "search", "tool": e["tool"], "query": e["query"]} for e in t["events"] if e["type"] == "search"]
            traces.append({"query_id": t["query_id"], "status": t["status"], "events": events, "citations": t["citations"]})
            support = [s.strip() == "1" for s in r["citation_support"].split(";") if s.strip()]
            review = {"query_id": r["query_id"], "citation_support": support, "reason": r["reason"]}
            if r["answerable"] == "1":
                review["answer_grade"] = int(r["answer_grade_0_1_2"])
                review["context_grade"] = int(r["context_grade_0_1_2"])
            else:
                review["abstention_correct"] = r["abstention_correct"].strip() == "1"
            reviews.append(review)
        write_json(REVIEW / f"{config}_test_cases.json", cases)
        write_json(REVIEW / f"{config}_test_traces.json", traces)
        write_json(REVIEW / f"{config}_test_reviews.json", reviews)
        result = aggregate(cases, traces, reviews)
        grades = Counter(r["context_grade"] for r in reviews if "context_grade" in r)
        result["context_grade"] = {"0": grades[0], "1": grades[1], "2": grades[2],
                                   "N": sum(grades.values()),
                                   "mean": round((grades[1] + 2 * grades[2]) / sum(grades.values()), 2) if grades else None}
        report[config] = result
        g, c = result["grounded_answer"], result["citation_validity"]
        print(f"{config}: answer 0/1/2 = {g['0']}/{g['1']}/{g['2']} (TB {g['mean']:.2f}) | context 0/1/2 = "
              f"{grades[0]}/{grades[1]}/{grades[2]} | citation hỗ trợ {c['n']}/{c['N']} | "
              f"từ chối đúng {result['abstention']['n']}/{result['abstention']['N']} | "
              f"từ chối nhầm {result['false_abstention']['n']}/{result['false_abstention']['N']}")
    write_json(REVIEW / "summary_test.json", {"grader": "Đỗ Thị Thanh Bình (tác giả)", **report})
    print("Đã lưu results/review/summary_test.json")


if __name__ == "__main__":
    main()
