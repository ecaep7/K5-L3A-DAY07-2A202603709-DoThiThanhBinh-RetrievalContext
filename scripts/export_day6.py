"""Xuất dữ liệu Day 6 sang định dạng Day 7.

    python scripts/export_day6.py

- Chunk: đọc thẳng từ pgvector của Day 6 (index B = chia theo đoạn văn) -> data/chunks.json
- Câu hỏi: đọc benchmark/questions.csv của repo Day 6, thêm 4 câu thiếu bằng chứng
  (data/unanswerable.json) -> data/questions.json
- Kiểm tra: mọi evidence nằm trọn trong một chunk đúng nguồn và trang; đủ 15+2 dev, 5+2 test.
Không tạo vector mới: Day 7 dùng lại đúng các vector đã lưu ở Day 6.
"""
import argparse
import csv
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DAY6_QUESTIONS = ROOT.parent / "K5-L3A-Day06-2A202603709-DataIngestionEngineering" / "benchmark" / "questions.csv"
INDEX = "B"

# Thay đổi nhãn so với Day 6, ghi rõ lý do (xem data/README_day7.md).
# q10: đoạn evidence 2 câu của Day 6 nằm vắt qua hai chunk B (p37-p09 | p37-p10), nên theo quy
# ước Day 7 (evidence phải nằm trọn trong một chunk) không chunk nào đạt được. Câu thứ hai một
# mình đã trả lời câu hỏi "vì sao", nên Day 7 dùng câu đó làm evidence.
GOLD_OVERRIDES = {
    "q10": {"page": 37, "evidence": "Failing to react quickly enough can lead to missed opportunities, yet acting "
                                    "too quickly can lead to organizational resources being poorly allocated to "
                                    "projects with no chance of success."},
}


def canon(text: str) -> str:
    """Chuẩn hóa để so khớp (giống Day 6): NFKC, gộp khoảng trắng, bỏ dấu cách sau '-'/'—'."""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text))
    return re.sub(r"(?<=[-—]) ", "", text).strip()


def export_chunks(database_url: str) -> list[dict]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("""
            SELECT chunk_id, document_id, source, page, chapter, printed_page, char_start, char_end,
                   text, content_hash, model
            FROM chunks WHERE strategy = %s ORDER BY page, char_start""", (INDEX,)).fetchall()
    return [{"id": r[0], "text": r[8], "source_id": r[1], "source": r[2], "page": r[3],
             "metadata": {"chapter": r[4], "printed_page": r[5], "char_start": r[6], "char_end": r[7],
                          "day6_index": INDEX, "embedding_model": r[10], "content_hash": r[9]}}
            for r in rows]


def convert_questions(day6_csv: Path, unanswerable: list[dict]) -> list[dict]:
    out = []
    with open(day6_csv, encoding="utf-8") as f:
        for q in csv.DictReader(f):
            gold = [{"source_id": q["gold_source_id"], "page": int(q["gold_page"]), "evidence": q["evidence_quote"]}]
            if q["alt_gold_page"]:
                gold.append({"source_id": q["gold_source_id"], "page": int(q["alt_gold_page"]),
                             "evidence": q["alt_evidence_quote"]})
            item = {"id": q["id"], "split": q["split"], "type": q["type"], "question": q["question"],
                    "expected_answer": q["expected_answer"], "answerable": True, "gold": gold}
            if q["id"] in GOLD_OVERRIDES:
                o = GOLD_OVERRIDES[q["id"]]
                item["gold"][0] = {"source_id": q["gold_source_id"], "page": o["page"], "evidence": o["evidence"]}
                item["day6_evidence"] = q["evidence_quote"]
            if q["filter_chapter"]:
                item["filter"] = {"chapter": int(q["filter_chapter"])}   # phạm vi người dùng nêu trong câu hỏi
            out.append(item)
    return out + unanswerable


def validate(chunks: list[dict], questions: list[dict]) -> None:
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk id bị trùng"
    for q in questions:
        if not q["answerable"]:
            continue
        for g in q["gold"]:
            found = [c["id"] for c in chunks if c["source_id"] == g["source_id"] and c["page"] == g["page"]
                     and canon(g["evidence"]) in canon(c["text"])]
            if not found:
                raise SystemExit(f"{q['id']}: evidence trang {g['page']} không nằm trọn trong chunk nào")
            g["chunk_ids"] = found   # chỉ để người chấm tra cứu; không bao giờ đưa vào agent/retrieval
    counts = Counter((q["split"], q["answerable"]) for q in questions)
    need = {("dev", True): 15, ("dev", False): 2, ("test", True): 5, ("test", False): 2}
    for key, n in need.items():
        assert counts[key] >= n, f"thiếu câu {key}: {counts[key]}/{n}"
    print("Số câu:", {f"{s}/{'có đáp án' if a else 'thiếu evidence'}": n for (s, a), n in sorted(counts.items())})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day6-questions", type=Path, default=DAY6_QUESTIONS)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    chunks = export_chunks(os.environ["DATABASE_URL"])
    unanswerable = json.loads((ROOT / "data" / "unanswerable.json").read_text(encoding="utf-8"))
    questions = convert_questions(args.day6_questions, unanswerable)
    validate(chunks, questions)
    (ROOT / "data" / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "data" / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Đã ghi data/chunks.json ({len(chunks)} chunk, index {INDEX}) và data/questions.json ({len(questions)} câu)")


if __name__ == "__main__":
    main()
