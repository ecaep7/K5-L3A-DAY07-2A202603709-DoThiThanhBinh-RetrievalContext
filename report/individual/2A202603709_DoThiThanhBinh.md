# Báo cáo Day 7

**Đỗ Thị Thanh Bình · 2A202603709 · L3A**

## Dữ liệu và benchmark

- **Nguồn, quyền sử dụng, số trang và số chunk:**
  - **Nguồn:** *Principles of Management* (OpenStax), ©2026 Rice University, giấy phép CC BY-NC-SA 4.0. Dùng chương 1–2, trang PDF 21–63, gồm **41 trang nội dung** (cách tính trang theo manifest Day 6).
  - **Corpus:** 356 chunk của index B Day 6 (chia theo đoạn văn, tối đa 500 ký tự), xuất thẳng từ bảng `chunks` trong pgvector bằng `scripts/export_day6.py` → [data/chunks.json](../../data/chunks.json). Text trích dùng cho mục đích học tập phi thương mại, ghi nguồn và chia sẻ cùng giấy phép.

- **Vector store, embedding model, phiên bản và số chiều:**
  - **Embedding:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers 6.3.0), 384 chiều, chạy local, vector chuẩn hóa độ dài 1.
  - **Vector store:** PostgreSQL 16.16 + pgvector 0.8.7 của Day 6 (Docker, cổng 55433), khoảng cách cosine, tìm chính xác.
  - **Kiểm tra tương thích:** câu hỏi được nhúng bằng cùng model. `DenseRetriever` đối chiếu cột `model` của index với model đang dùng và dừng chương trình nếu khác. Không tạo index mới.

- **Agent model, cách chạy và phân chia dev/test:**
  - **Model:** `claude-haiku-5-5` qua Claude API, dùng lớp tương thích OpenAI SDK, temperature 0. Chi phí tính bằng số token × 0,10 / 0,50 USD mỗi 1 triệu token (vào / ra).
  - **Lệnh chạy:** `python -m src.run_agent --split <dev|test> --configs ...` (chi tiết trong [README](../../README.md)).
  - **Phân chia:** 24 câu, gồm dev 15 câu có đáp án + 2 câu thiếu bằng chứng, test 5 + 2. 20 câu có đáp án giữ nguyên câu hỏi và split của Day 6. Tập test Day 6 chỉ chạy một lần và chưa dùng để chỉnh hệ thống; ở Day 7 mọi lựa chọn dựa trên dev, test chạy một lần sau khi chốt.

- **Cách xác định câu có/thiếu evidence và tiêu chí chấm:**
  - **Câu có đáp án:** mỗi câu có `gold` (nguồn, trang, evidence nguyên văn). Script kiểm tra mọi evidence nằm trọn trong một chunk đúng trang. 7 câu có thêm evidence thay thế ở mục Key Terms (trang 59).
  - **Thay đổi so với Day 6 — q10:** đoạn evidence 2 câu vắt qua hai chunk `p37-p09` | `p37-p10`, nên không thể nằm trọn trong một chunk. Day 7 dùng câu thứ hai (đủ trả lời "vì sao") và giữ bản cũ ở `day6_evidence`.
  - **Câu thiếu bằng chứng:** 4 câu gần chủ đề (u01 người đặt tên "groupthink", u02 số giờ làm việc mỗi tuần trong nghiên cứu Kotter, u03 nominal group technique, u04 mô hình Vroom-Yetton). Sự vắng mặt được kiểm tra bằng cách dò từ khóa trên toàn bộ 41 trang, không dựa vào top-k ([data/unanswerable.json](../../data/unanswerable.json)).
  - **Định nghĩa hit:** chunk đúng nguồn, đúng trang của một phần tử `gold` và chứa trọn evidence sau chuẩn hóa Unicode và khoảng trắng.
  - **Nhãn chấm tay:** chấm theo thang 0/1/2 của [BENCHMARK.md](../../BENCHMARK.md). `gold` và `expected_answer` không bao giờ được đưa vào agent hay retriever.

## Retrieval và thử nghiệm

**Ba phương pháp:** cả ba chạy trên cùng 356 chunk, cùng câu hỏi và cùng bộ nhãn, đều lọc `chapter` khi người dùng nêu chương (q07, q08, q18, q20).
- **dense:** tìm vector gần nhất trong pgvector.
- **lexical:** BM25 (k1 = 1,5, b = 0,75), trong đó Postgres `to_tsvector('english')` lo tách từ, bỏ stopword và đưa về gốc từ.
- **hybrid:** gộp top-20 của dense và top-20 của lexical bằng RRF với k = 60.

Hai nhóm cột Hit đo hai thứ khác nhau:
- Với A, B, C: Hit@1 và Hit@3 đo bằng **câu hỏi gốc** (`results/retrieval/`).
- Với D, E: đo trên **lần tìm đầu tiên do model tự đặt câu** (`first_search_*` trong `results/agent/`), vì đây là các cấu hình agent.

Context Evidence Rate luôn đo trên context cuối cùng đưa cho model. Mọi cấu hình đều dùng top-k = 3, không rerank.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Baseline (A_dense) | dense, k=3, filter chương do người dùng nêu, không rerank, 1 lần tìm, 6000 ký tự | Phương pháp Day 6 | dev | 11/15 (73%) | 13/15 (87%) | 12/15 (80%) | 54 ms/câu truy xuất; agent 2,98 s/câu, 0,00632 USD / 17 câu |
| Phương pháp 2 (B_lexical) | BM25, k=3, như trên | Bắt được từ khóa hiếm, nhanh | dev | 12/15 (80%) | 12/15 (80%) | 12/15 (80%) | 15 ms; 2,81 s/câu, 0,00541 USD |
| Phương pháp 3 (C_hybrid) | RRF dense + BM25 (top-20 mỗi bên), k=3 | Hai bên bù nhau | dev | 13/15 (87%) | 14/15 (93%) | 12/15 (80%) | 70 ms; 3,02 s/câu, 0,00612 USD |
| Cải thiện 1 (D_hybrid_multi) | hybrid, k=3, **tối đa 3 lần tìm**, 6000 ký tự | Cho model tìm lại bằng từ khác sẽ sửa lỗi lệch từ vựng (q14) | dev | 12/15 (80%)* | 12/15 (80%)* | 14/15 (93%) | 3,21 s/câu, 0,00657 USD |
| Cải thiện 2 (E_hybrid_multi_nb) | như D + **kèm chunk liền trước/sau**, 9000 ký tự | Đưa phần đoạn văn bị cắt sang chunk kế bên vào context (q10) | dev | 12/15 (80%)* | 13/15 (87%)* | **15/15 (100%)** | 2,87 s/câu, 0,00768 USD |
| Cấu hình đã chọn (E) | như trên | Chốt trên dev | test | 2/5 (40%)* · câu gốc hybrid 4/5 | 5/5 (100%)* · câu gốc hybrid 4/5 | **5/5 (100%)** | 4,41 s/câu, 0,00479 USD / 7 câu |
| Baseline (A_dense) | như dòng 1 | | test | 3/5 (60%)* · câu gốc dense 4/5 | 4/5 (80%)* · câu gốc dense 4/5 | 4/5 (80%) | 2,72 s/câu, 0,00256 USD / 7 câu |

\* Hit của lần tìm đầu do model đặt câu. Trên test, khi dùng câu hỏi gốc, cả ba phương pháp đều đạt Hit@1 4/5 và Hit@3 4/5. Recall@10: dense 4/5, lexical 5/5, hybrid 4/5. Nguồn số liệu: [results/retrieval/summary_test.json](../../results/retrieval/summary_test.json).

**D và E vừa là cấu hình cải thiện vừa là cách dùng tìm kiếm nhiều bước.** Model tự viết lại câu tìm, nên ngoài kết quả của câu hỏi gốc (bảng trên, hàng A–C), từng bước tìm đều được lưu trong trace (`events`). Tổng chi phí cho toàn bộ thử nghiệm khoảng 0,04 USD.

**Hai lỗi dev, nguyên nhân, cách thử và lý do chọn** (chi tiết: [results/SELECTION_dev.md](../../results/SELECTION_dev.md)):

1. **q14 — lệch từ vựng.**
   - **Hiện tượng:** câu hỏi dùng cụm "mental shortcuts", còn evidence `p42-p00` dùng từ "heuristics" và là phần đuôi của một đoạn văn bắt đầu ở trang 41. Với câu hỏi gốc, đoạn này không lọt top-10 ở cả ba phương pháp. A, B, C tìm một lần rồi trung thực trả lời `INSUFFICIENT_EVIDENCE`, tức là từ chối nhầm.
   - **Cách thử:** cho model tìm lại. Ở D, model tìm 3 lần; lần thứ ba với câu "heuristics can result in systematic errors…" lấy được `p42-p00` và trả lời đúng. E lấy được ngay ở lần tìm thứ hai.
2. **q10 — bằng chứng nằm ở chunk kế bên.**
   - **Hiện tượng:** lần tìm đầu chỉ đưa lên `p37-p09` ("Waiting too long…"), còn ý "vì sao" nằm ở chunk liền sau `p37-p10`. A, B, C, D chỉ trả lời được một phần.
   - **Cách thử:** kèm thêm chunk liền kề. E nhận `p37-p10` như hàng xóm của `p37-p09` và trả lời đủ ý.
   - **Ghi chú:** lỗi này cũng giải thích vì sao q10 trượt ở Day 6.

**Tiêu chí chọn:**
1. Context Evidence Rate cao nhất.
2. Không từ chối nhầm, đồng thời vẫn từ chối đúng 2/2.
3. Chi phí dưới 0,001 USD/câu và thời gian dưới 5 s/câu.

E là cấu hình duy nhất đạt 15/15. Tiêu chí này được viết ra sau khi đã xem kết quả agent trên dev, nhưng trước khi chạy test.

## Agent và đánh giá

- **Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi:**
  - **Công cụ:** một công cụ `search_documents(query)`. Model tự viết câu tìm. Phạm vi chương do người dùng nêu được hệ thống áp vào bộ lọc chứ không để model tự quyết.
  - **Điều kiện dừng:** model trả lời mà không gọi thêm công cụ, hoặc hết `max_searches` (1 hoặc 3). Nếu model gọi tìm khi đã hết lượt, code trả về thông báo "Search limit reached" và buộc model trả lời từ context đang có. Ngoài ra có chặn vòng lặp ở `max_searches + 2` lượt gọi model.
  - **Chọn context:**
    - Bỏ chunk đã hiển thị cho model trước đó (chỉ báo "Already shown").
    - Ở cấu hình E, kèm chunk liền trước và liền sau theo thứ tự trong sách, vẫn trong phạm vi chương.
    - Cộng dồn số ký tự; chunk làm vượt budget (6000 hoặc 9000 ký tự) bị bỏ và ghi vào `dropped_by_budget`.
  - **Trích dẫn và từ chối:** model phải trích `[chunk-id]` sau mỗi câu, hoặc mở đầu câu trả lời bằng `INSUFFICIENT_EVIDENCE:`. Code tách các id được trích và đối chiếu với context; id không có trong context được ghi vào `citations_not_in_context`.
  - **Xử lý lỗi:** lỗi model hoặc vector store được ghi `status: "error"` kèm thông báo, không thay bằng kết quả giả. Nội dung tài liệu được dặn rõ là dữ liệu, không phải chỉ dẫn.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| A_dense / test | 7/7 (100%) | 1 lần tìm × 7 câu; 17 lượt gọi model | 1/0/4 — **1,60** | 8/8 (100%) | 4/4 câu trả lời | 2/2 (100%) | 1/5 (20%) |
| E_hybrid_multi_nb / test | 7/7 (100%) | tìm 1 lần: 4 câu, 2 lần: 1 câu, 3 lần: 2 câu | 0/0/5 — **2,00** | 11/11 (100%) | 5/5 câu trả lời | 2/2 (100%) | 0/5 (0%) |
| (tham khảo) 5 cấu hình / dev | 17/17 mỗi cấu hình | A–C: 1 lần; D: 1/2/3 lần = 13/1/3 câu; E: 15/1/1 câu | chưa chấm tay | mọi id đều nằm trong context | 14/14 (A–C), 15/15 (D, E) | 2/2 mọi cấu hình | A–C 1/15, D–E 0/15 |

Điểm context chấm tay trên test (0/1/2): A 1/0/4, E 0/0/5. Citation hợp lệ là số trích dẫn mà người chấm đã đọc và xác nhận đoạn được trích **thật sự chứng minh** câu được gắn vào, chứ không chỉ là id có trong context.

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| q04 (E, test) | có đáp án, so sánh | Lần 1: "disturbance handler role Mintzberg managerial roles" → trang 23, 23, 25. Lần 2: "entrepreneur role managers initiate change projects" → trang 25, 25, 27 | Entrepreneur khởi xướng thay đổi; disturbance handler phải phản ứng một cách bị động trước hoàn cảnh [p25-p01][p25-p02] | Context 2, trả lời 2, citation 2/2: lần tìm thứ hai lấy được đúng trang 25 |
| u04 (E, test) | thiếu bằng chứng | 3 lần tìm: "Vroom-Yetton model…", "leader-participation model Vroom Jago…", "normative decision model…" → không đoạn nào nhắc mô hình này | `INSUFFICIENT_EVIDENCE:` đã tìm 3 lần, tài liệu không nhắc mô hình Vroom-Yetton | Từ chối đúng, không khẳng định vô căn cứ |
| q04 (A, test) | có đáp án — **lỗi** | 1 lần: "disturbance handler role Mintzberg managerial roles" → trang 23, 23, 26 (thiếu trang 25) | `INSUFFICIENT_EVIDENCE:` các đoạn chỉ nói về vai trò figurehead | Context 0, trả lời 0: tìm một lần không trúng, nên từ chối nhầm (cùng kiểu lỗi với q14 trên dev) |

- **Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí:**
  - **Trace:** `results/retrieval/<method>_<split>.json` và `results/agent/<config>_<split>.json`. Mỗi file ghi từng tool call, tham số, kết quả, context cuối, câu trả lời, citation, token, chi phí, thời gian và lỗi.
  - **Tổng hợp:** `results/*/summary_*.json`.
  - **Nhãn chấm tay:** [results/review/test_review.csv](../../results/review/test_review.csv), tổng hợp bằng `starter/agent_metrics.py` thành [results/review/summary_test.json](../../results/review/summary_test.json). Người chấm là tác giả.
  - **Lệnh chạy:** xem [README](../../README.md).
  - **Chi phí:** toàn bộ thử nghiệm khoảng 0,04 USD; embedding và vector store chạy local, không mất phí.

- **Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:**
  - **Trước/sau:**
    - Dev: Context Evidence Rate tăng từ 12/15 (A–C) lên 14/15 (D) rồi 15/15 (E); từ chối nhầm giảm từ 1/15 xuống 0/15.
    - Test: điểm câu trả lời tăng từ 1,60 (A) lên 2,00 (E). Lỗi q04 của A cùng kiểu với q14 trên dev, và lần tìm thứ hai của E sửa được.
  - **Model tự viết lại câu tìm:**
    - Ở q16 (test), câu hỏi cố ý tránh thuật ngữ, nên với câu hỏi gốc cả dense lẫn hybrid đều trượt (lexical chỉ tìm thấy ở hạng 7). Nhưng trong agent, Claude tự đặt câu tìm "escalation of commitment…" và tìm trúng ngay. Như vậy model đã dùng kiến thức chung để đổi cách diễn đạt sang đúng thuật ngữ của sách.
    - Câu trả lời vẫn bám tài liệu, vì có trích dẫn định nghĩa ở trang 44.
    - Hệ quả: Hit của lần tìm đầu trong agent khác với Hit của câu hỏi gốc. Vì vậy báo cáo ghi cả hai.
  - **Đánh đổi của E so với A trên test:**
    - Chi phí gấp khoảng 1,9 lần (0,00479 so với 0,00256 USD) và chậm hơn khoảng 1,6 lần (4,41 so với 2,72 s/câu). Phần tốn thêm chủ yếu nằm ở 2 câu thiếu bằng chứng: E tìm đủ 3 lần, mỗi câu khoảng 7 giây, rồi mới từ chối.
    - Context lớn hơn khoảng 4 lần (4393 so với 1108 ký tự trung bình).
    - Với bộ dữ liệu nhỏ này, chi phí tuyệt đối không đáng kể (khoảng 0,0007 USD/câu).
  - **Giới hạn:**
    - **Tập test nhỏ:** 5 + 2 câu, mỗi câu chiếm 20%.
    - **Một người chấm:** chỉ tác giả chấm tay, và chỉ chấm trên test; các cấu hình trên dev được so sánh bằng chỉ số tự động.
    - **Kết quả khó tái lập chính xác:** model tự đặt câu tìm, nên chạy lại có thể khác vài câu.
    - **Chi phí là ước tính:** tính từ số token × bảng giá, không phải hóa đơn. Thời gian đo trên một máy và có tính cả độ trễ mạng.
    - **Lớp kết nối:** Anthropic mô tả lớp tương thích OpenAI SDK là dành cho thử nghiệm và so sánh model.
    - **Phép khớp evidence quá chặt:** đòi khớp nguyên văn.
    - **Chunk chia trong từng trang:** đoạn văn vắt qua trang bị cắt đôi.
    - **Benchmark có hỗ trợ của AI:** câu hỏi Day 6 và 4 câu thiếu bằng chứng được soạn với hỗ trợ của Claude.
    - **Đã biết trước một lỗi của test:** từ Day 6 đã biết q16 trên test là câu khó. Thiết kế D và E chỉ dựa trên lỗi dev (q14, q10), nhưng không loại trừ hoàn toàn ảnh hưởng gián tiếp.
  - **Hướng mở rộng:**
    - Chia chunk nối qua ranh giới trang để khỏi cần kèm hàng xóm.
    - Thêm bước rerank.
    - Giới hạn số lần tìm cho câu đã rõ là thiếu bằng chứng, để giảm chi phí.
    - Thêm người chấm thứ hai và mở rộng tập test.

## Thử thách nâng cao (nếu thực hiện)

Không thực hiện.

---

**Sử dụng AI:** Claude (Anthropic) hỗ trợ giải thích, viết code, soạn câu hỏi thiếu bằng chứng và soạn bản nháp báo cáo này. Tác giả chạy toàn bộ thử nghiệm trên máy cá nhân, kiểm tra kết quả, tự chấm toàn bộ nhãn và đọc duyệt báo cáo.
