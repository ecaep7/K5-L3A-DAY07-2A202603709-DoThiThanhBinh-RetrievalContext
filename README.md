# Day 7 · Retrieval & Context Engineering — Đỗ Thị Thanh Bình (2A202603709)

Agent trả lời câu hỏi về 2 chương sách *Principles of Management* (OpenStax), dùng lại dữ liệu, embedding và vector store của Day 6. Agent tự gọi công cụ tìm kiếm, trả lời có trích dẫn `[chunk-id]` hoặc nói `INSUFFICIENT_EVIDENCE` khi tài liệu không đủ.

- **Corpus:** 356 chunk (index B Day 6, chia theo đoạn văn ≤ 500 ký tự), 41 trang nội dung, chương 1–2 ([data/README_day7.md](data/README_day7.md)).
- **Embedding / vector store:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 chiều, local) · PostgreSQL 16 + pgvector 0.8.7 của Day 6 (Docker, cổng 55433). Dùng lại vector đã lưu, không tạo index mới.
- **Model agent:** `claude-haiku-5-5` qua Claude API (lớp tương thích OpenAI SDK), temperature 0. Có thể đổi sang OpenRouter bằng `LLM_PROVIDER`.
- **Benchmark:** 24 câu — dev 15 có đáp án + 2 thiếu bằng chứng, test 5 + 2 ([data/questions.json](data/questions.json)).
- **3 phương pháp truy xuất:** dense (pgvector), lexical (BM25 trên từ gốc do Postgres tách), hybrid (RRF) — [src/retrievers.py](src/retrievers.py).
- **Cấu hình chọn trên dev:** `E_hybrid_multi_nb` = hybrid, tìm tối đa 3 lần, kèm chunk liền trước/sau, context ≤ 9000 ký tự ([results/SELECTION_dev.md](results/SELECTION_dev.md)).

## Kết quả chính

| | Split | Context Evidence Rate | Câu trả lời 0/1/2 (TB) | Citation hỗ trợ | Từ chối đúng | Từ chối nhầm | Chi phí | s/câu |
|---|---|---|---|---|---|---|---|---|
| A_dense (baseline) | test | 4/5 | 1/0/4 (1.60) | 8/8 | 2/2 | 1/5 | 0.00256 USD | 2.72 |
| **E_hybrid_multi_nb** | test | **5/5** | **0/0/5 (2.00)** | 11/11 | 2/2 | 0/5 | 0.00479 USD | 4.41 |

Nhãn chấm tay do tác giả chấm: [results/review/test_review.csv](results/review/test_review.csv), tổng hợp bằng `starter/agent_metrics.py`: [results/review/summary_test.json](results/review/summary_test.json). Phân tích đầy đủ: [report/individual/2A202603709_DoThiThanhBinh.md](report/individual/2A202603709_DoThiThanhBinh.md).

## Cấu trúc

```text
data/
  chunks.json, questions.json      xuất từ Day 6 (scripts/export_day6.py)
  unanswerable.json                4 câu thiếu bằng chứng + cách kiểm tra vắng mặt
  README_day7.md                   nguồn, giấy phép, schema, thay đổi so với Day 6
src/
  common.py                        cấu hình, chuẩn hóa so khớp evidence
  retrievers.py                    dense / lexical (BM25) / hybrid (RRF), cùng định dạng kết quả, lọc chapter
  eval_retrieval.py, run_retrieval.py   Hit@1, Evidence Hit@3, Recall@10, MRR@10 với câu hỏi gốc
  llm.py                           gọi Claude API / OpenRouter, ghi token, chi phí, thời gian
  agent.py                         vòng lặp agent, chọn context, dedup, budget, trích dẫn, xử lý lỗi
  configs.py                       5 cấu hình A–E
  eval_agent.py, run_agent.py      chỉ số tự động của agent
scripts/
  export_day6.py                   xuất chunk + câu hỏi từ Day 6, kiểm tra evidence
  check_llm.py                     kiểm tra kết nối model và tool calling
  make_review_sheet.py, summarize_reviews.py   bảng chấm tay và tổng hợp nhãn
results/
  retrieval/                       trace + summary của 3 phương pháp (dev, test)
  agent/                           trace từng câu (tool call, context, câu trả lời, citation, token, chi phí, lỗi) + summary
  review/                          nhãn chấm tay test và tổng hợp
  SELECTION_dev.md                 so sánh trên dev, 2 lỗi, tiêu chí và lựa chọn (trước khi chạy test)
starter/, tests/                   code mẫu của đề bài (không sửa)
```

## Cài đặt

Cần Python 3.11+, Docker Desktop và repo Day 6 nằm cạnh repo này với database đang chạy (xem README Day 6).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker start day6_student_starter-postgres-1
```

Tạo file `.env` (không commit):

```
DATABASE_URL=postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-5-5
ANTHROPIC_API_KEY=<key của bạn>
```

## Chạy lại

```powershell
python scripts/export_day6.py                       # data/chunks.json, data/questions.json (đã có sẵn trong repo)
python scripts/check_llm.py                         # kiểm tra model gọi được công cụ
python -m src.run_retrieval --split dev             # 3 phương pháp, câu hỏi gốc
python -m src.run_agent --split dev --configs A_dense B_lexical C_hybrid D_hybrid_multi E_hybrid_multi_nb
# chốt cấu hình trên dev (results/SELECTION_dev.md), sau đó chạy test một lần:
python -m src.run_retrieval --split test
python -m src.run_agent --split test --configs A_dense E_hybrid_multi_nb
python scripts/make_review_sheet.py                 # tạo bảng chấm tay (không ghi đè nhãn đã có)
python scripts/summarize_reviews.py                 # tổng hợp nhãn bằng starter/agent_metrics.py
python -m unittest discover -s tests -v             # test mock của starter đề bài
```

Câu tìm kiếm do model tự đặt nên chạy lại có thể khác vài câu so với trace đã lưu.

## Chi phí và thời gian

Toàn bộ thử nghiệm (5 cấu hình × 17 câu dev, 2 cấu hình × 7 câu test, 1 lượt kiểm tra) tốn khoảng **0.04 USD** Claude API, tính từ số token × giá `claude-haiku-5-5` (0.10 / 0.50 USD mỗi 1M token vào/ra). Embedding và vector store chạy local, không tốn phí. Thời gian từng câu nằm trong trace (`totals.latency_s`).

## Dữ liệu và giấy phép

*Principles of Management*, OpenStax, ©2026 Rice University, giấy phép CC BY-NC-SA 4.0. Access for free at openstax.org. Text trích trong `data/` và `results/` dùng cho mục đích học tập phi thương mại, chia sẻ lại cùng giấy phép. File PDF không có trong repo; cách tải và tạo lại ở README Day 6.

## Sử dụng AI

Claude (Anthropic) hỗ trợ giải thích, viết code và soạn 4 câu thiếu bằng chứng. Tác giả chạy toàn bộ thử nghiệm trên máy cá nhân, kiểm tra kết quả và **tự chấm toàn bộ nhãn** trong `results/review/test_review.csv`. Lớp tương thích OpenAI SDK của Claude API được Anthropic mô tả là dành cho thử nghiệm, so sánh model; phù hợp phạm vi bài lab.

## Hướng dẫn gốc của lab

[GUIDE.md](GUIDE.md) · [BENCHMARK.md](BENCHMARK.md) · [RUBRIC.md](RUBRIC.md) · [RULES.md](RULES.md) · [SUBMISSION.md](SUBMISSION.md) · [ADVANCED.md](ADVANCED.md)

## Trang demo

Mở `demo/index.html` bằng trình duyệt (nhấp đúp, không cần server, không gọi API). Trang gồm: kết quả retrieval và 5 cấu hình agent, 3 ví dụ demo (có bằng chứng / thiếu bằng chứng / lỗi), hai lỗi dev trước và sau cải tiến, và trình xem trace từng câu (câu tìm kiếm, kết quả, context, trích dẫn, chấm tay).

## Thử thách nâng cao: kết quả test **29/30 = 96,67%** (ngưỡng ≥ 90%)

### Tài liệu
*From the Last Mile to the Next Mile – 2022 Vietnam Poverty and Equity Assessment*, World Bank, 2022, giấy phép CC BY 3.0 IGO, **232 trang PDF**, tiếng Anh. Tải tại http://hdl.handle.net/10986/37952 (mục *English PDF*, 13.53 MB) và lưu thành `data/advanced/vietnam-poverty-equity-2022.pdf`. File PDF không đẩy lên repo. Trích dẫn dùng **số trang PDF** (1–232); `page_label` là số in ở chân trang.

### Index (`src/adv_index.py`)
| | |
|---|---|
| Chunk văn bản | 621 đoạn, lấy từ lớp chữ PDF (pymupdf), mỗi chunk ≤ 1.100 ký tự, thuộc đúng 1 trang. Bỏ header/footer và chữ nằm trong vùng hình. |
| Chunk hình | 223: 163 biểu đồ, 34 bảng, 21 sơ đồ, 5 bản đồ. Vùng hình xác định từ chú thích "Figure/Table x.y" trong lớp chữ PDF, kéo tới dòng "Source:"; bảng không có Source thì dừng ở đường kẻ cuối; 3 bảng in ngang được xoay ảnh. Nội dung do claude-haiku-5-5 đọc ảnh trang (150 dpi): bảng chép đủ ô, biểu đồ ghi trục/chú giải/giá trị (giá trị không in trên hình ghi "~"), bản đồ/sơ đồ mô tả chú giải và các ô. |
| Kiểm tra với bản gốc | Mỗi chunk hình lưu `bbox` (toạ độ PDF), ảnh crop (`data/advanced/crops/`, tạo lại bằng bước build), chữ thật trong vùng (`pdf_text`) và danh sách số mà model đọc nhưng không có trong lớp chữ PDF (`numbers_not_in_pdf_text`, 163 hình: chủ yếu là giá trị đọc ước lượng "~"). Đã so 5 trang thử (52, 61, 90, 96, 182) với bản gốc trước khi chạy cả tài liệu. |
| Lưu trữ | Bảng `adv_chunks` trong PostgreSQL + pgvector, embedding MiniLM 384 chiều (giống Day 6). |
| Không xử lý | Trang 1, 2, 230–232 (bìa, trang trống). 34 trang không có chunk văn bản (bìa, mục lục, trang chỉ có bảng/hình): nội dung các trang hình nằm trong chunk hình. Công thức toán in dạng ảnh (trang 73, 171–172) bị xếp loại "diagram", ít giá trị tra cứu. Bảng kéo dài nhiều trang (Table 8.1/8.2) chỉ trang có chú thích được ghép đúng nhãn. |
| Chi phí | Vision: 0,15 USD cho bản cache cuối (145 trang); tổng đã chi kể cả chạy thử/chạy lại khoảng 0,32 USD. |

Thống kê đầy đủ: `data/advanced/index/stats.json`. Cache vision từng trang: `data/advanced/vision/`.

### Benchmark (`data/advanced/benchmark.json`, bảng đọc `data/advanced/benchmark_review.md`)
Dev 18 câu (15 có đáp án + 3 thiếu bằng chứng), test 30 câu: bảng 6, ảnh/sơ đồ/bản đồ 5, biểu đồ 5, multi-hop 4, text 4, thiếu bằng chứng 6. Mỗi câu có nhóm, đáp án, phép tính, evidence (trang PDF + ô/hàng/cột, vùng hình hoặc đoạn văn nguyên văn), lý do; câu thiếu bằng chứng có cách kiểm tra. Mọi trích dẫn và số in trên trang được kiểm tra tự động với lớp chữ PDF (`scripts/adv_make_benchmark.py`). Dev/test được chia trước khi chạy agent; không đưa đáp án, evidence hay gold vào agent.

### Agent và chọn cấu hình (`src/adv_agent.py`, `results/advanced/SELECTION_dev.md`)
Agent gọi công cụ `search_documents` (tối đa 4 lần), trả lời có trích dẫn `[pea-p048-v02]` kèm tên bảng/hình và trang, hoặc `INSUFFICIENT_EVIDENCE`. So 4 cấu hình trên dev, cùng model claude-haiku-5-5:

| Cấu hình | Trích dẫn trúng evidence | Số khớp đáp án | Từ chối đúng | Chi phí dev |
|---|---:|---:|---:|---:|
| V0 chỉ chunk văn bản (mốc) | 2/15 | 0,51 | 3/3 | 0,028 USD |
| V1 dense, chữ + hình | 12/15 | 0,90 | 3/3 | 0,027 USD |
| **V2 hybrid RRF, chữ + hình, top 5** | **15/15** | **1,00** | 3/3 | **0,019 USD** |
| V3 hybrid, top 8 | 14/15 | 1,00 | 3/3 | 0,024 USD |

Chốt V2 theo tiêu chí viết trước khi chạy test. V0 cho thấy không có index hình thì phần lớn câu bảng/biểu đồ/sơ đồ không trả lời được.

### Kết quả test (chạy một lần, `results/advanced/agent/V2_hybrid_test.json`)
Chấm tay từng câu bằng cách đối chiếu bản PDF gốc: `results/advanced/review/test_review.csv` (cột `pass`, `reason`); tổng hợp `results/advanced/review/summary_test.json`.

| Nhóm | Đạt |
|---|---:|
| Bảng | 6/6 |
| Ảnh, sơ đồ, bản đồ | 5/5 |
| Biểu đồ | 4/5 |
| Multi-hop | 4/4 |
| Text | 4/4 |
| Thiếu bằng chứng | 6/6 |
| **Tổng** | **29/30 = 96,67%** |

Lỗi hệ thống 0; chi phí test 0,031 USD; trung bình 5,1 s/câu.

**Câu không đạt: at16** (tỷ lệ nghèo theo dân tộc 2010–2020). Agent lấy số từ hai đoạn văn (trang 28, 103) đã làm tròn (9%, 57%→27%, Kinh 2020 = 1,3%) thay vì Figure 3.1 trang 102 (56,8→27,2; 9,4→1,2); chunk biểu đồ không vào context vì câu hỏi trùng nhiều từ với đoạn văn tóm tắt. Hướng sửa: khi đoạn văn chỉ có số làm tròn, nhắc agent tìm thêm bảng/biểu đồ gốc; hoặc ưu tiên chunk hình khi câu hỏi hỏi số liệu theo năm.

### Giới hạn
- Câu biểu đồ trong test chủ yếu là biểu đồ có in nhãn số; test chưa đo độ chính xác của giá trị đọc ước lượng "~".
- Mô tả hình do model tạo; chỉ kiểm tra tự động phần số có trong lớp chữ PDF và kiểm tra bằng mắt các trang thử, các vùng evidence của benchmark.
- Benchmark do Claude soạn và tác giả duyệt (có đối chiếu ảnh trang gốc), nên có thể nghiêng về kiểu câu hỏi mà pipeline xử lý được. Test chỉ 30 câu, một người chấm.
- Sau dev đã thay 1 câu test (at30) vì lý do nội dung tài liệu, trước khi chạy test; ghi trong `SELECTION_dev.md`.

### Chạy lại
```
python -X utf8 -m src.adv_index --step text
python -X utf8 -m src.adv_index --step vision      # dùng cache trong data/advanced/vision, không gọi lại model
python -X utf8 -m src.adv_index --step build
python -X utf8 -m src.adv_index --step load
python -X utf8 -m src.adv_agent --split dev --configs V0_text_only V1_dense V2_hybrid V3_hybrid_k8
python -X utf8 -m src.adv_agent --split test --configs V2_hybrid
python -X utf8 scripts/adv_make_review.py          # tạo file chấm (không ghi đè file đã chấm)
python -X utf8 scripts/adv_summarize_review.py
```

Sử dụng AI ở phần nâng cao: Claude viết code index/agent, soạn và duyệt benchmark (theo yêu cầu của tác giả). Tác giả chạy toàn bộ trên máy cá nhân và chấm đạt/không đạt 30 câu test bằng cách đối chiếu bản gốc.
