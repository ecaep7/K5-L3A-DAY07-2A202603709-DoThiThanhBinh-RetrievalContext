"""Tạo file chấm tay cho test (phần nâng cao): results/advanced/review/test_review.csv.

    python -X utf8 scripts/adv_make_review.py

Mỗi dòng một câu test: câu hỏi, đáp án mong đợi, evidence trong bản gốc (trang PDF, bảng/hình, vị trí),
câu trả lời và trích dẫn của agent. Người chấm mở PDF gốc, đối chiếu rồi điền cột pass (1 = đạt, 0 = không đạt)
và reason. Cách chấm theo ADVANCED.md: câu có đáp án đạt khi đúng và đủ, đúng đơn vị/điều kiện/phép tính,
trích dẫn xác định được trang và vùng evidence; câu thiếu bằng chứng đạt khi từ chối và không thêm khẳng định
thiếu căn cứ; lỗi hệ thống/timeout/không có kết quả là không đạt.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "V2_hybrid"
bench = {q["id"]: q for q in json.loads((ROOT / "data/advanced/benchmark.json").read_text(encoding="utf-8")) if q["split"] == "test"}
traces = json.loads((ROOT / f"results/advanced/agent/{CONFIG}_test.json").read_text(encoding="utf-8"))
out = ROOT / "results/advanced/review/test_review.csv"
out.parent.mkdir(parents=True, exist_ok=True)
if out.exists():
    raise SystemExit(f"{out} đã có (có thể đã chấm). Đổi tên hoặc xóa file cũ trước nếu thật sự muốn tạo lại.")

rows = []
for t in traces:
    q = bench[t["query_id"]]
    if q["answerable"]:
        evidence = " || ".join(f"PDF trang {e['page']} (in {e['page_label']}): "
                               + (f"{e['label']} - {e['location']} - giá trị: {e['values']}" if e["kind"] != "text" else f"đoạn văn: \"{e['quote']}\"")
                               for e in q["evidence"])
        expected = q["expected_answer"] + (f" [phép tính: {q['calculation']}]" if q.get("calculation") else "")
    else:
        evidence, expected = "Cách kiểm tra: " + q["absence_check"], "Từ chối (INSUFFICIENT_EVIDENCE), không suy đoán"
    cites = "; ".join(f"{c['id']} = PDF trang {c['page']}" + (f" {c['label']}" if c.get("label") else f" ({c['kind']})")
                      if c["page"] else f"{c['id']} (KHÔNG có trong context)" for c in t["citations"])
    rows.append({"id": q["id"], "group": q["group"], "question": q["question"], "expected_answer": expected,
                 "evidence_in_original": evidence, "agent_status": t["status"] + (f" ({t['error']})" if t.get("error") else ""),
                 "agent_answer": t["answer"] or "", "agent_citations": cites, "pass": "", "reason": ""})
with out.open("w", encoding="utf-8-sig", newline="") as f:      # utf-8-sig để Excel mở đúng tiếng Việt
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"Đã tạo {out.relative_to(ROOT)} ({len(rows)} câu). Điền cột pass (1/0) và reason, lưu dạng CSV UTF-8.")
