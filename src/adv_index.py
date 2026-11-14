"""Phần nâng cao: index báo cáo World Bank "2022 Vietnam Poverty and Equity Assessment" (232 trang PDF).

Ý tưởng: tách tài liệu thành 2 loại "mảnh" (chunk), cùng nằm trong một bảng pgvector `adv_chunks`:
  - text   : đoạn văn lấy thẳng từ lớp chữ của PDF (pymupdf), mỗi chunk thuộc đúng một trang.
  - visual : mỗi bảng / biểu đồ / bản đồ / sơ đồ một chunk. Vùng hình được xác định bằng chú thích
             "Figure x.y" / "Table x.y" trong lớp chữ PDF (từ dòng chú thích tới dòng "Source:").
             Nội dung hình do model vision (Claude) đọc từ ảnh trang, kèm chữ có thật trong vùng đó
             (nhãn trục, ô bảng, Note, Source) lấy từ lớp chữ PDF để đối chiếu.

Các bước (chạy lần lượt):
  python -m src.adv_index --step text                 # không tốn tiền: đọc chữ + tìm vùng hình
  python -m src.adv_index --step vision --pages 25,53 # thử vài trang trước (tốn ít tiền)
  python -m src.adv_index --step vision               # toàn bộ trang có hình (có cache, chạy lại không gọi lại)
  python -m src.adv_index --step build                # ghép chunk text + visual, kiểm tra số liệu, cắt ảnh
  python -m src.adv_index --step load                 # embedding MiniLM + nạp vào Postgres
"""
import argparse
import base64
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import DATA, DEFAULT_EMBEDDING_MODEL, database_url, write_json

ADV = DATA / "advanced"
PDF = ADV / "vietnam-poverty-equity-2022.pdf"
INDEX_DIR = ADV / "index"
VISION_DIR = ADV / "vision"
CROPS_DIR = ADV / "crops"
TABLE = "adv_chunks"

DOCUMENT = {
    "doc_id": "pea2022",
    "title": "From the Last Mile to the Next Mile - 2022 Vietnam Poverty and Equity Assessment",
    "publisher": "World Bank",
    "year": 2022,
    "url": "http://hdl.handle.net/10986/37952",
    "file": "English PDF (13.53 MB) on the World Bank Open Knowledge Repository",
    "license": "CC BY 3.0 IGO",
    "page_numbering": "page = số trang của file PDF (1-232); page_label = số in ở chân trang",
}

# Trang không xử lý hình (ghi lý do vào thống kê): bìa, mục lục / danh mục hình, bìa sau.
SKIP_VISION = {1: "bìa trước", 2: "trang trống/bản quyền", 230: "trang trống", 231: "bìa sau", 232: "bìa sau"}
HEADER_Y, FOOTER_Y = 50, 745          # chữ ở trên/dưới mức này là header/footer chạy
CAPTION = re.compile(r"^(Figure|Table|Map)\s+((?:[A-Z][.\s]?)?\d+(?:\.\d+)*[a-z]?|[A-Z]\.\d+)[.:]?\s")
LIST_PAGE_MIN_CAPTIONS = 8            # trang có nhiều chú thích như vậy là danh mục hình, không phải hình
MAX_CHUNK_CHARS = 1100


def open_pdf():
    import pymupdf
    return pymupdf.open(PDF)


def clean(text: str) -> str:
    text = text.replace("­", "").replace("−", "-")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # nối từ bị ngắt dòng bằng gạch nối
    return re.sub(r"\s+", " ", text).strip()


def page_label(blocks) -> str | None:
    """Số trang in ở chân trang, vd 'From the Last Mile to the Next Mile 41' -> '41', 'xvi' ..."""
    for b in blocks:
        if b[1] > FOOTER_Y - 10:
            t = clean(b[4])
            m = re.match(r"^([0-9]+|[ivxlc]+)\s", t) or re.search(r"\s([0-9]+|[ivxlc]+)$", t)
            if m:
                return m.group(1)
    return None


def section_of(blocks) -> str | None:
    for b in blocks:
        if b[1] < HEADER_Y and len(clean(b[4])) > 3:
            t = clean(b[4])
            return t[0].upper() + t[1:].lower()
    return None


def column_of(x0: float, x1: float, width: float) -> tuple[float, float]:
    mid = width / 2
    if x1 <= mid + 6:
        return 36.0, mid
    if x0 >= mid - 6:
        return mid, width - 36.0
    return 36.0, width - 36.0


def overlaps_x(b, col) -> bool:
    return min(b[2], col[1]) - max(b[0], col[0]) > 0.5 * min(b[2] - b[0], col[1] - col[0])


def find_regions(page_no: int, blocks, width: float, rules: list | None = None) -> list[dict]:
    """Vùng của từng hình/bảng có chú thích: từ dòng chú thích tới hết dòng 'Source:' cùng cột."""
    caps, seen = [], set()
    for b in blocks:   # chú thích là khối ngắn; đoạn văn dài mở đầu bằng "Figure 6.13 shows..." thì bỏ qua
        m = CAPTION.match(b[4].strip())
        if m and HEADER_Y < b[1] < FOOTER_Y and len(clean(b[4])) <= 250 and m.group(0).strip() not in seen:
            seen.add(m.group(0).strip())
            caps.append(b)
    if len(caps) >= LIST_PAGE_MIN_CAPTIONS:
        return []
    regions = []
    for cap in caps:
        m = CAPTION.match(cap[4].strip())
        label = f"{m.group(1)} {m.group(2)}"
        if cap[3] - cap[1] > 3 * (cap[2] - cap[0]):   # bảng xoay ngang (chữ dọc): lấy cả trang
            regions.append({"page": page_no, "label": label, "title": CAPTION.sub("", clean(cap[4])).strip(),
                            "kind_hint": "table" if label.startswith("Table") else "figure",
                            "bbox": [36.0, HEADER_Y, round(width - 36.0, 1), FOOTER_Y],
                            "region_ends_at": "rotated page", "rotated": True})
            continue
        col = column_of(cap[0], cap[2], width)
        below = sorted([b for b in blocks if b[1] > cap[1] + 1 and overlaps_x(b, col) and b[1] < FOOTER_Y],
                       key=lambda b: b[1])
        # tiêu đề có thể xuống dòng sang khối kế tiếp nằm sát bên dưới
        title_parts, last = [clean(cap[4])], cap
        for b in below:
            if 0 <= b[1] - last[3] < 4 and len(clean(b[4])) < 120 and not re.match(r"^[\d\-.,%K ]+$", clean(b[4])):
                title_parts.append(clean(b[4]))
                last = b
            else:
                break
        bottom, ends = None, "source"
        for b in below:
            if CAPTION.match(b[4].strip()) and b is not cap:
                bottom, ends = b[1] - 4, "next caption"
                break
            if any(re.match(r"^\s*Sources?\s*:", line) for line in b[4].splitlines()):
                bottom = b[3] + 2
                break
        if bottom is None and label.startswith("Table") and rules:
            # bảng không có dòng Source: lấy tới đường kẻ ngang cuối cùng của bảng (+ dòng Note ngay dưới)
            lines = sorted(y for (x0, y, x1) in rules if y > last[3] and min(x1, col[1]) - max(x0, col[0]) > 0.4 * (col[1] - col[0]))
            end = None
            for y in lines:
                if end is not None and y - end > 150:
                    break
                end = y
            if end is not None:
                note = next((b for b in below if 0 <= b[1] - end < 25
                             and any(re.match(r"^\s*Notes?\s*:", l) for l in b[4].splitlines())), None)
                bottom, ends = (note[3] + 2, "table rules + note") if note else (end + 3, "table rules")
        if bottom is None:   # không có dòng Source: dừng ở dòng Note:, hoặc trước đoạn văn rộng đầu tiên bên dưới
            note = next((b for b in below if any(re.match(r"^\s*Notes?\s*:", l) for l in b[4].splitlines())), None)
            para = next((b for b in below if len(clean(b[4])) > 250 and is_prose(b[4])
                         and b[2] - b[0] >= 0.8 * (col[1] - col[0] - 30)), None)
            if note and (not para or note[1] < para[1]):
                bottom, ends = note[3] + 2, "note"
            elif para:
                bottom, ends = para[1] - 4, "next paragraph"
            else:
                bottom, ends = FOOTER_Y, "page bottom"
        title = " ".join(title_parts)
        title = CAPTION.sub("", title).strip() or title
        regions.append({"page": page_no, "label": label, "title": title,
                        "kind_hint": "table" if label.startswith("Table") else ("map" if label.startswith("Map") else "figure"),
                        "bbox": [round(col[0], 1), round(cap[1] - 4, 1), round(col[1], 1), round(bottom, 1)],
                        "region_ends_at": ends})
    return regions


def inside(b, bbox) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return bbox[0] - 2 <= cx <= bbox[2] + 2 and bbox[1] - 2 <= cy <= bbox[3] + 2


def is_prose(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    avg = sum(len(l) for l in lines) / len(lines)
    return len(clean(text)) >= 40 and avg >= 28


def step_text() -> None:
    doc = open_pdf()
    pages, chunks, regions = [], [], []
    for i, page in enumerate(doc):
        page_no = i + 1
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        width = page.rect.width
        segs: dict[int, list] = {}      # đường kẻ ngang của bảng thường bị cắt theo từng ô: gộp theo tung độ
        for d in page.get_drawings():
            r = d["rect"]
            if r.height < 2.5 and r.width > 20:
                segs.setdefault(round(r.y1), []).append((r.x0, r.x1))
        rules = [(min(a for a, _ in v), y, max(b for _, b in v)) for y, v in segs.items()]
        regs = find_regions(page_no, blocks, width, rules)
        for r in regs:
            r["pdf_text"] = clean(" | ".join(b[4] for b in blocks if inside(b, r["bbox"])))
            r["notes"] = [clean(b[4]) for b in blocks if inside(b, r["bbox"])
                          and any(re.match(r"^\s*(Notes?|Sources?)\s*:", line) for line in b[4].splitlines())]
        regions += regs
        body = [b for b in blocks if HEADER_Y <= b[1] <= FOOTER_Y and not any(inside(b, r["bbox"]) for r in regs)]
        prose = [b for b in body if is_prose(b[4])]
        mid = width / 2
        prose.sort(key=lambda b: (0 if b[0] < mid - 6 else 1, b[1]))     # đọc hết cột trái rồi cột phải
        label, section = page_label(blocks), section_of(blocks)
        n, buf = 0, []

        def flush():
            nonlocal n, buf
            if buf:
                n += 1
                text = " ".join(clean(x[4]) for x in buf)
                chunks.append({"id": f"pea-p{page_no:03d}-t{n:02d}", "kind": "text", "page": page_no,
                               "page_label": label, "section": section, "label": None, "title": None,
                               "bbox": [round(min(x[0] for x in buf), 1), round(min(x[1] for x in buf), 1),
                                        round(max(x[2] for x in buf), 1), round(max(x[3] for x in buf), 1)],
                               "text": text})
                buf = []

        for b in prose:
            size = sum(len(clean(x[4])) for x in buf)
            if buf and size + len(clean(b[4])) > MAX_CHUNK_CHARS:
                flush()
            buf.append(b)
        flush()
        pages.append({"page": page_no, "page_label": label, "section": section, "text_chunks": n,
                      "regions": [r["label"] for r in regs], "drawings": len(page.get_drawings()),
                      "images": len(page.get_images()), "chars": len(page.get_text())})
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    write_json(INDEX_DIR / "pages.json", pages)
    write_json(INDEX_DIR / "text_chunks.json", chunks)
    write_json(INDEX_DIR / "regions.json", regions)
    no_text = [p["page"] for p in pages if p["text_chunks"] == 0]
    print(f"{len(pages)} trang · {len(chunks)} chunk text · {len(regions)} vùng hình/bảng có chú thích "
          f"(Figure {sum(r['label'].startswith('Figure') for r in regions)}, "
          f"Table {sum(r['label'].startswith('Table') for r in regions)})")
    print(f"Trang không có đoạn văn nào: {no_text}")


# ---------------------------------------------------------------- vision
VISION_PROMPT = """This is page {page} of the World Bank report "2022 Vietnam Poverty and Equity Assessment".
Read the informative visual elements on the page image and transcribe them faithfully. Do not use outside knowledge.

Captioned elements detected on this page (from the PDF text layer):
{labels}

For EVERY captioned element above, and for any other informative visual without a caption \
(a map, diagram, infographic or chart; skip logos, page decoration and plain body text), give:
- "label": the caption label exactly as listed above, or null if it has no caption
- "kind": one of "table", "chart", "map", "diagram", "infographic", "photo"
- "bbox": only for elements with label null: [x0, y0, x1, y1] on a 0-1000 scale of page width/height
- "description": a faithful transcription:
  * table: a markdown table with every row and column, headers and units exactly as printed
  * chart: chart type; axis titles and units; legend / series names; the categories; every value that is \
printed on the chart; if values are not printed, approximate readings for each category and series written \
with "~" (for example ~12); then one sentence on the visible pattern
  * map: what is mapped, the legend classes, and which regions or areas look highest / lowest
  * diagram or infographic: all text and numbers shown and how the parts are connected
  If a chart has several panels, describe each panel.

Return ONLY JSON: {{"elements": [{{"label": ..., "kind": ..., "bbox": ..., "description": ...}}]}}"""


def vision_pages(pages: list[dict]) -> list[int]:
    out = []
    for p in pages:
        if p["page"] in SKIP_VISION:
            continue
        if p["regions"] or p["drawings"] > 40 or p["images"] > 0:
            out.append(p["page"])
    return out


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def vision_one(page_no: int, doc, regions_by_page: dict, llm, force: bool) -> dict:
    out_path = VISION_DIR / f"p{page_no:03d}.json"
    if out_path.exists() and not force:
        cached = json.loads(out_path.read_text(encoding="utf-8"))
        if cached.get("ok"):
            return {"page": page_no, "cached": True, **cached.get("usage", {})}
    import pymupdf
    regs = regions_by_page.get(page_no, [])
    rotate = 90 if any(r.get("rotated") for r in regs) else 0      # trang in ngang: xoay ảnh cho chữ đứng thẳng
    png = doc[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72).prerotate(rotate)).tobytes("png")
    labels = "\n".join(f"- {r['label']}: {r['title']}" for r in regs) or "- (none detected)"
    messages = [{"role": "user", "content": [
        {"type": "text", "text": VISION_PROMPT.format(page=page_no, labels=labels)},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}]
    record = {"page": page_no, "model": llm.model, "detected_labels": [r["label"] for r in regs], "ok": False}
    try:
        message, usage = llm.chat(messages, max_tokens=8000)
        record["raw"] = message.content or ""
        record["usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "cost_usd", "latency_s")}
        record["elements"] = parse_json(record["raw"]).get("elements", [])
        record["ok"] = True
    except Exception as exc:   # ghi lỗi, không bịa nội dung; chạy lại sẽ thử lại trang này
        record["error"] = f"{type(exc).__name__}: {exc}"
    write_json(out_path, record)
    return {"page": page_no, "cached": False, "ok": record["ok"], "error": record.get("error"),
            **record.get("usage", {})}


def step_vision(only: list[int] | None, force: bool, workers: int) -> None:
    from .llm import LLM
    pages = json.loads((INDEX_DIR / "pages.json").read_text(encoding="utf-8"))
    regions = json.loads((INDEX_DIR / "regions.json").read_text(encoding="utf-8"))
    by_page: dict[int, list] = {}
    for r in regions:
        by_page.setdefault(r["page"], []).append(r)
    targets = only or vision_pages(pages)
    llm = LLM()
    doc = open_pdf()
    VISION_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Gửi {len(targets)} trang cho {llm.model} (trang đã có cache sẽ bỏ qua)...")
    results, started = [], time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(lambda p: vision_one(p, doc, by_page, llm, force), targets):
            results.append(r)
            flag = "cache" if r.get("cached") else ("OK" if r.get("ok") else f"LỖI {r.get('error')}")
            print(f"  trang {r['page']:3d}: {flag}")
    fresh = [r for r in results if not r.get("cached")]
    cost = sum(r.get("cost_usd", 0) for r in fresh)
    failed = [r["page"] for r in results if not r.get("cached") and not r.get("ok")]
    print(f"Xong {len(results)} trang trong {time.perf_counter() - started:.0f} s · gọi mới {len(fresh)} trang · "
          f"chi phí lần này {cost:.4f} USD · lỗi: {failed or 'không có'}")


# ---------------------------------------------------------------- build
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)*")


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text.replace("−", "-"))}


LABEL = re.compile(r"(Figure|Table|Map)\s+((?:[A-Z][.\s]?)?\d+(?:\.\d+)*[a-z]?|[A-Z]\.\d+)", re.I)


def norm_label(label: str | None) -> str:
    """'Figure O.1: Economic growth...' và 'Figure O.1' -> 'figureo.1' (model hay chép cả tiêu đề vào nhãn)."""
    m = LABEL.match((label or "").strip())
    return re.sub(r"\s+", "", m.group(0).lower()).rstrip(".") if m else ""


def step_build(crop_dpi: int) -> None:
    import pymupdf
    pages = {p["page"]: p for p in json.loads((INDEX_DIR / "pages.json").read_text(encoding="utf-8"))}
    regions = json.loads((INDEX_DIR / "regions.json").read_text(encoding="utf-8"))
    text_chunks = json.loads((INDEX_DIR / "text_chunks.json").read_text(encoding="utf-8"))
    doc = open_pdf()
    CROPS_DIR.mkdir(parents=True, exist_ok=True)
    visual, problems, cost = [], [], 0.0
    vision = {}
    for f in sorted(VISION_DIR.glob("p*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        vision[rec["page"]] = rec
        cost += rec.get("usage", {}).get("cost_usd", 0)
    by_page: dict[int, list] = {}
    for r in regions:
        by_page.setdefault(r["page"], []).append(r)
    for page_no in sorted(set(by_page) | set(vision)):
        rec = vision.get(page_no, {})
        elements = rec.get("elements", []) if rec.get("ok") else []
        if page_no in vision and not rec.get("ok"):
            problems.append({"page": page_no, "problem": "vision lỗi", "detail": rec.get("error")})
        used, n = set(), 0
        page = doc[page_no - 1]
        W, H = page.rect.width, page.rect.height
        items = []
        for r in by_page.get(page_no, []):
            match = next((k for k, e in enumerate(elements) if k not in used
                          and norm_label(e.get("label")) == norm_label(r["label"])), None)
            if match is None:
                if page_no not in vision:
                    problems.append({"page": page_no, "problem": "trang chưa chạy vision", "detail": r["label"]})
                    continue
                problems.append({"page": page_no, "problem": "model không mô tả hình có chú thích", "detail": r["label"]})
                items.append((r, {"kind": r["kind_hint"], "description": ""}))
            else:
                used.add(match)
                items.append((r, elements[match]))
        for k, e in enumerate(elements):
            if k in used or e.get("kind") == "decorative":
                continue
            bb = e.get("bbox") or [0, 0, 1000, 1000]
            try:
                bbox = [round(bb[0] * W / 1000, 1), round(bb[1] * H / 1000, 1), round(bb[2] * W / 1000, 1), round(bb[3] * H / 1000, 1)]
            except (TypeError, IndexError):
                bbox = [0, 0, W, H]
            blocks = [b for b in page.get_text("blocks") if b[6] == 0]
            items.append(({"page": page_no, "label": e.get("label"), "title": None, "bbox": bbox,
                           "pdf_text": clean(" | ".join(b[4] for b in blocks if inside(b, bbox))), "notes": [],
                           "region_ends_at": "bbox do model ước lượng"}, e))
        for r, e in items:
            n += 1
            cid = f"pea-p{page_no:03d}-v{n:02d}"
            desc = (e.get("description") or "").strip()
            kind = e.get("kind") or r.get("kind_hint") or "figure"
            head = f"{r['label']}. {r['title']}" if r.get("label") and r.get("title") else (r.get("label") or f"Untitled {kind}")
            text = f"{head}\n[{kind} on page {page_no}]\n{desc}"
            if r.get("notes"):
                text += "\n" + "\n".join(r["notes"])
            unverified = sorted(numbers(desc) - numbers(r.get("pdf_text", "")) - numbers(r.get("title") or ""),
                                key=lambda x: (len(x), x))
            crop = CROPS_DIR / f"{cid}.png"
            rect = pymupdf.Rect(*r["bbox"]) & page.rect
            if not rect.is_empty:
                page.get_pixmap(dpi=crop_dpi, clip=rect).save(crop)
            visual.append({"id": cid, "kind": kind, "page": page_no, "page_label": pages[page_no]["page_label"],
                           "section": pages[page_no]["section"], "label": r.get("label"), "title": r.get("title"),
                           "bbox": r["bbox"], "region_ends_at": r.get("region_ends_at"),
                           "crop": f"data/advanced/crops/{cid}.png", "text": text, "pdf_text": r.get("pdf_text", ""),
                           "numbers_not_in_pdf_text": unverified, "vision_model": rec.get("model")})
    chunks = text_chunks + visual
    chunks.sort(key=lambda c: (c["page"], c["kind"] != "text", c["id"]))
    write_json(INDEX_DIR / "chunks.json", chunks)
    kinds: dict[str, int] = {}
    for c in visual:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    stats = {"document": DOCUMENT, "pdf_pages": len(pages),
             "text_chunks": len(text_chunks), "visual_chunks": len(visual), "visual_by_kind": kinds,
             "captioned_regions": len(regions),
             "pages_sent_to_vision": sorted(vision), "vision_cost_usd": round(cost, 4),
             "pages_without_text_chunks": [p for p, v in pages.items() if v["text_chunks"] == 0],
             "pages_not_processed_for_visuals": {str(p): why for p, why in SKIP_VISION.items() if p <= len(pages)},
             "problems": problems,
             "visuals_with_numbers_not_in_pdf_text": sum(1 for c in visual if c["numbers_not_in_pdf_text"]),
             "config": {"max_chunk_chars": MAX_CHUNK_CHARS, "vision_render_dpi": 150, "crop_dpi": crop_dpi,
                        "embedding_model": DEFAULT_EMBEDDING_MODEL}}
    write_json(INDEX_DIR / "stats.json", stats)
    print(f"{len(chunks)} chunk = {len(text_chunks)} text + {len(visual)} visual {kinds}")
    print(f"Vấn đề cần xem: {len(problems)} · hình có số không thấy trong lớp chữ PDF (thường là số đọc ước lượng ~): "
          f"{stats['visuals_with_numbers_not_in_pdf_text']} · chi phí vision tổng {cost:.4f} USD")


# ---------------------------------------------------------------- load
def step_load() -> None:
    import psycopg
    from sentence_transformers import SentenceTransformer
    chunks = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
    model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    vectors = model.encode([c["text"] for c in chunks], normalize_embeddings=True, convert_to_numpy=True,
                           batch_size=32, show_progress_bar=True)
    with psycopg.connect(database_url()) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
        conn.execute(f"""CREATE TABLE {TABLE} (id text PRIMARY KEY, seq int, kind text, page int, page_label text,
                         section text, label text, title text, text text, model text, embedding vector(384))""")
        with conn.cursor() as cur:
            for seq, (c, v) in enumerate(zip(chunks, vectors)):
                cur.execute(f"INSERT INTO {TABLE} VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                            (c["id"], seq, c["kind"], c["page"], c["page_label"], c["section"], c["label"],
                             c["title"], c["text"], DEFAULT_EMBEDDING_MODEL,
                             "[" + ",".join(f"{x:.7f}" for x in v) + "]"))
        count = conn.execute(f"SELECT kind, count(*) FROM {TABLE} GROUP BY kind ORDER BY kind").fetchall()
    print(f"Đã nạp vào bảng {TABLE}: {dict(count)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True, choices=["text", "vision", "build", "load"])
    ap.add_argument("--pages", help="vd 25,53,61 (chỉ cho bước vision)")
    ap.add_argument("--force", action="store_true", help="gọi lại vision kể cả trang đã có cache")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--crop-dpi", type=int, default=110)
    a = ap.parse_args()
    if a.step == "text":
        step_text()
    elif a.step == "vision":
        step_vision([int(x) for x in a.pages.split(",")] if a.pages else None, a.force, a.workers)
    elif a.step == "build":
        step_build(a.crop_dpi)
    else:
        step_load()


if __name__ == "__main__":
    main()
