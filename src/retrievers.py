"""Ba phương pháp truy xuất trên cùng 356 chunk (index B của Day 6).

dense   : embedding câu hỏi bằng MiniLM, tìm vector gần nhất trong pgvector (giống Day 6).
lexical : BM25 trên từ khóa. Postgres tách từ, bỏ stopword và đưa về gốc từ (to_tsvector 'english');
          điểm BM25 tính trong Python để có trọng số IDF (ts_rank của Postgres không có IDF).
hybrid  : gộp danh sách của dense và lexical bằng Reciprocal Rank Fusion (RRF) - cộng 1/(60 + hạng),
          không cộng thẳng điểm vì thang điểm hai bên khác nhau.

Mọi phương pháp nhận cùng tham số `filters` (chỉ cột chapter/page/source_id) và trả về cùng định dạng:
id, text, source_id, source, page, chapter, score, rank, method.
"""
import math
import re
from collections import Counter
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .common import DEFAULT_EMBEDDING_MODEL, INDEX, database_url

FILTERABLE = {"chapter": "chapter", "page": "page", "source_id": "document_id"}
CHUNK_COLUMNS = "chunk_id AS id, text, document_id AS source_id, source, page, chapter"


def _where(filters: dict[str, Any] | None) -> tuple[str, list]:
    clauses, params = ["strategy = %s"], [INDEX]
    for key, value in (filters or {}).items():
        if key not in FILTERABLE:
            raise ValueError(f"Không cho phép lọc theo '{key}'")
        clauses.append(f"{FILTERABLE[key]} = %s")
        params.append(value)
    return " AND ".join(clauses), params


def _rank(rows: list[dict], method: str) -> list[dict]:
    for i, r in enumerate(rows, start=1):
        r["rank"], r["method"] = i, method
        r["score"] = round(float(r["score"]), 6)
    return rows


class DenseRetriever:
    name = "dense"

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, embedder=None) -> None:
        if embedder is None:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer(model_name)
        self.model = embedder
        self.model_name = model_name
        with psycopg.connect(database_url()) as conn:
            stored = conn.execute("SELECT DISTINCT model FROM chunks WHERE strategy = %s", (INDEX,)).fetchall()
        if [r[0] for r in stored] != [model_name]:
            raise SystemExit(f"Index lưu bằng model {stored}, câu hỏi đang dùng {model_name}: không tương thích")

    def embed(self, query: str) -> list[float]:
        return self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0].tolist()

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[dict]:
        where, params = _where(filters)
        vector = "[" + ",".join(f"{x:.7f}" for x in self.embed(query)) + "]"
        sql = (f"SELECT {CHUNK_COLUMNS}, 1 - (embedding <=> %s::vector) AS score FROM chunks "
               f"WHERE {where} ORDER BY embedding <=> %s::vector LIMIT %s")
        with psycopg.connect(database_url()) as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, [vector, *params, vector, top_k])
            return _rank(cur.fetchall(), self.name)


def _lexemes(tsvector_text: str) -> Counter:
    """Đọc tsvector dạng "'manag':1,5 'decis':3" thành {gốc từ: số lần xuất hiện}."""
    return Counter({m.group(1): len(m.group(2).split(",")) for m in re.finditer(r"'([^']+)':([\d,A-D]+)", tsvector_text)})


class LexicalRetriever:
    """BM25 (k1=1.5, b=0.75). Chỉ số được dựng một lần khi khởi tạo, từ chính bảng chunks của Day 6."""
    name = "lexical"

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        with psycopg.connect(database_url()) as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT {CHUNK_COLUMNS}, to_tsvector('english', text)::text AS tsv "
                        "FROM chunks WHERE strategy = %s", (INDEX,))
            self.chunks = cur.fetchall()
        for c in self.chunks:
            c["tf"] = _lexemes(c.pop("tsv"))
            c["length"] = sum(c["tf"].values())
        self.avg_length = sum(c["length"] for c in self.chunks) / len(self.chunks)
        df = Counter(term for c in self.chunks for term in c["tf"])
        n = len(self.chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def query_terms(self, query: str) -> list[str]:
        with psycopg.connect(database_url()) as conn:
            tsv = conn.execute("SELECT to_tsvector('english', %s)::text", (query,)).fetchone()[0]
        return list(_lexemes(tsv))

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[dict]:
        _where(filters)   # cùng kiểm tra tên cột lọc như dense
        terms = self.query_terms(query)
        scored = []
        for c in self.chunks:
            if any(c[k] != v for k, v in (filters or {}).items()):
                continue
            score = 0.0
            for t in terms:
                tf = c["tf"].get(t, 0)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * c["length"] / self.avg_length)
                    score += self.idf[t] * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append({k: c[k] for k in ("id", "text", "source_id", "source", "page", "chapter")} | {"score": score})
        scored.sort(key=lambda r: (-r["score"], r["id"]))
        return _rank(scored[:top_k], self.name)


class HybridRetriever:
    """RRF: điểm = tổng 1/(rrf_k + hạng) qua các danh sách; lấy `candidates` kết quả đầu của mỗi bên."""
    name = "hybrid"

    def __init__(self, dense: DenseRetriever, lexical: LexicalRetriever,
                 candidates: int = 20, rrf_k: int = 60) -> None:
        self.dense, self.lexical, self.candidates, self.rrf_k = dense, lexical, candidates, rrf_k

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[dict]:
        fused: dict[str, dict] = {}
        for retriever in (self.dense, self.lexical):
            for r in retriever.search(query, self.candidates, filters):
                entry = fused.setdefault(r["id"], {k: r[k] for k in ("id", "text", "source_id", "source", "page", "chapter")}
                                         | {"score": 0.0, "from": {}})
                entry["score"] += 1 / (self.rrf_k + r["rank"])
                entry["from"][retriever.name] = r["rank"]
        ranked = sorted(fused.values(), key=lambda r: (-r["score"], r["id"]))
        return _rank(ranked[:top_k], self.name)
