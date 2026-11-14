"""Đường dẫn, cấu hình và hàm dùng chung."""
import json
import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
INDEX = "B"   # index chia theo đoạn văn của Day 6
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

load_dotenv(ROOT / ".env")


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise SystemExit("Thiếu DATABASE_URL trong .env")
    return url


def canon(text: str) -> str:
    """Chuẩn hóa để so khớp evidence (giống Day 6): NFKC, gộp khoảng trắng, bỏ dấu cách sau '-'/'—'."""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text))
    return re.sub(r"(?<=[-—]) ", "", text).strip()


def load_questions(split: str | None = None) -> list[dict]:
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    return [q for q in questions if split is None or q["split"] == split]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
