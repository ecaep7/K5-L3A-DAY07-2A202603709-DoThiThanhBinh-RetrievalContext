"""Tạo bảng chấm tay cho các lượt agent trên test: results/review/test_review.csv (mở bằng Excel).

    python scripts/make_review_sheet.py

Không ghi đè nếu file đã có, để nhãn đã chấm không bị mất.
Cột cần điền:
  context_grade_0_1_2  (câu có đáp án) 0 = context không có evidence; 1 = có nhưng thiếu điều kiện hoặc nguồn; 2 = đủ evidence và nguồn
  answer_grade_0_1_2   (câu có đáp án) 0 = sai/thiếu evidence (từ chối cũng là 0); 1 = đúng một phần; 2 = đúng và đủ
  citation_support     một số 1/0 cho MỖI citation theo đúng thứ tự cột citations, cách nhau bằng dấu ;  (ví dụ 1;1;0)
  abstention_correct   (câu thiếu bằng chứng) 1 = agent thực sự từ chối và không khẳng định vô căn cứ; 0 = không
  reason               lý do ngắn
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import load_questions  # noqa: E402

CONFIGS = ["A_dense", "E_hybrid_multi_nb"]
OUT = ROOT / "results" / "review" / "test_review.csv"


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"{OUT.relative_to(ROOT)} đã có, không ghi đè nhãn đã chấm")
    questions = {q["id"]: q for q in load_questions("test")}
    rows = []
    for config in CONFIGS:
        traces = json.loads((ROOT / "results" / "agent" / f"{config}_test.json").read_text(encoding="utf-8"))
        for t in traces:
            q = questions[t["query_id"]]
            context = {c["id"]: c for c in t["context"]}
            cited = "\n\n".join(f"[{cid}] trang {context[cid]['page']}\n{context[cid]['text']}" if cid in context
                                else f"[{cid}] KHÔNG CÓ TRONG CONTEXT" for cid in t["citations"])
            gold = "\n".join(f"trang {g['page']}: {g['evidence']}" for g in q.get("gold", []))
            rows.append({
                "config": config, "query_id": t["query_id"], "answerable": int(q["answerable"]),
                "question": q["question"], "expected_answer": q.get("expected_answer", ""),
                "gold_evidence": gold or q.get("absence_reason", ""),
                "status": t["status"], "answer": t["answer"] or "",
                "searches": " | ".join(e["query"] for e in t["events"] if e["type"] == "search"),
                "citations": ";".join(t["citations"]), "cited_passages": cited,
                "context_ids": " ".join(c["id"] for c in t["context"]),
                "auto_context_has_evidence": t.get("eval", {}).get("context_has_evidence", ""),
                "context_grade_0_1_2": "", "answer_grade_0_1_2": "", "citation_support": "",
                "abstention_correct": "", "reason": ""})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã tạo {OUT.relative_to(ROOT)}: {len(rows)} dòng cần chấm")


if __name__ == "__main__":
    main()
