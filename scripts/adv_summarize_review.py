"""Tổng hợp nhãn chấm tay test (phần nâng cao): n/N toàn bộ và theo nhóm, lỗi, thời gian, chi phí.

    python -X utf8 scripts/adv_summarize_review.py

Đọc results/advanced/review/test_review.csv (đã chấm) và trace results/advanced/agent/V2_hybrid_test.json;
ghi results/advanced/review/summary_test.json và in bảng. Ngưỡng bonus: >= 90% số câu test, không làm tròn.
"""
import csv
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "V2_hybrid"
rows = list(csv.DictReader((ROOT / "results/advanced/review/test_review.csv").open(encoding="utf-8-sig")))
traces = {t["query_id"]: t for t in json.loads((ROOT / f"results/advanced/agent/{CONFIG}_test.json").read_text(encoding="utf-8"))}
missing = [r["id"] for r in rows if r["pass"].strip() not in ("0", "1")]
if missing:
    raise SystemExit(f"Chưa chấm (cột pass phải là 0 hoặc 1): {missing}")

groups = ["table", "image", "chart", "multi_hop", "text", "unanswerable"]
by_group = {g: {"pass": 0, "N": 0} for g in groups}
for r in rows:
    by_group[r["group"]]["N"] += 1
    by_group[r["group"]]["pass"] += int(r["pass"])
n, N = sum(int(r["pass"]) for r in rows), len(rows)
rate = Fraction(n, N)
summary = {
    "config": CONFIG, "model": "claude-haiku-5-5",
    "pass": f"{n}/{N}", "pass_rate_percent": round(float(rate) * 100, 2), "meets_90_percent": rate >= Fraction(9, 10),
    "by_group": {g: f"{v['pass']}/{v['N']}" for g, v in by_group.items()},
    "failed": [{"id": r["id"], "group": r["group"], "reason": r["reason"]} for r in rows if r["pass"].strip() == "0"],
    "system_errors": [q for q, t in traces.items() if t["status"] == "error"],
    "total_cost_usd": round(sum(t["totals"]["cost_usd"] for t in traces.values()), 4),
    "avg_latency_s": round(sum(t["totals"]["latency_s"] for t in traces.values()) / len(traces), 2),
    "llm_calls": sum(t["totals"]["llm_calls"] for t in traces.values()),
    "graded_by": "tác giả, đối chiếu bản PDF gốc",
}
path = ROOT / "results/advanced/review/summary_test.json"
path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Đạt {n}/{N} = {summary['pass_rate_percent']}%  ->  {'ĐẠT ngưỡng 90%' if summary['meets_90_percent'] else 'CHƯA đạt ngưỡng 90%'}")
for g in groups:
    print(f"  {g:13s} {by_group[g]['pass']}/{by_group[g]['N']}")
print(f"Lỗi hệ thống: {len(summary['system_errors'])} | chi phí {summary['total_cost_usd']} USD | {summary['avg_latency_s']} s/câu")
print(f"Đã lưu {path.relative_to(ROOT)}")
