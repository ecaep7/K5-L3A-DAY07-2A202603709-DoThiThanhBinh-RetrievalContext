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

## Thử thách nâng cao (đang làm, chưa báo điểm)

Tài liệu: *From the Last Mile to the Next Mile – 2022 Vietnam Poverty and Equity Assessment* (World Bank 2022, CC BY 3.0 IGO, 232 trang PDF), tải tại http://hdl.handle.net/10986/37952 (English PDF, 13.53 MB) và lưu thành `data/advanced/vietnam-poverty-equity-2022.pdf` (không đẩy lên repo).

Đã xong:
- Index (`src/adv_index.py`): 844 chunk = 621 đoạn văn (lớp chữ PDF) + 223 bảng/biểu đồ/bản đồ/sơ đồ (vùng hình xác định từ chú thích trong lớp chữ PDF; nội dung do claude-haiku-5-5 đọc ảnh trang, cache ở `data/advanced/vision/`; số liệu đối chiếu tự động với lớp chữ PDF). Thống kê: `data/advanced/index/stats.json`.
- Benchmark (`data/advanced/benchmark.json`, bảng duyệt `data/advanced/benchmark_review.md`): dev 18 câu, test 30 câu (24 có đáp án + 6 thiếu bằng chứng).

Còn lại: chọn cấu hình agent trên dev, chạy test một lần, chấm đạt/không đạt từng câu.

Tái tạo index:
```
python -X utf8 -m src.adv_index --step text
python -X utf8 -m src.adv_index --step vision
python -X utf8 -m src.adv_index --step build
python -X utf8 -m src.adv_index --step load
```
