"""Chấm ranking: Hit@1, Evidence Hit@3, Recall@10, MRR@10 - chỉ trên câu có đáp án.

Một chunk là "hit" khi đúng nguồn + trang của một phần tử gold và chứa trọn evidence của phần tử đó
(cùng định nghĩa với Day 6). Câu thiếu bằng chứng không vào mẫu số.
"""
from .common import canon


def is_hit(chunk: dict, question: dict) -> bool:
    text = canon(chunk["text"])
    return any(chunk["source_id"] == g["source_id"] and chunk["page"] == g["page"] and canon(g["evidence"]) in text
               for g in question["gold"])


def score_query(question: dict, results: list[dict]) -> dict:
    hits = [is_hit(r, question) for r in results]
    first = hits.index(True) + 1 if any(hits) else None
    return {"hit1": bool(hits[:1] and hits[0]), "hit3": any(hits[:3]), "hit10": any(hits[:10]),
            "first_hit_rank": first, "rr": 1 / first if first and first <= 10 else 0.0,
            "top3_pages": [r["page"] for r in results[:3]],
            "top3_ids": [r["id"] for r in results[:3]]}


def summarize(scored: list[dict]) -> dict:
    n = len(scored)
    return {"N": n,
            "hit1": sum(s["hit1"] for s in scored), "hit3": sum(s["hit3"] for s in scored),
            "hit10": sum(s["hit10"] for s in scored),
            "mrr10": round(sum(s["rr"] for s in scored) / n, 3) if n else None}
