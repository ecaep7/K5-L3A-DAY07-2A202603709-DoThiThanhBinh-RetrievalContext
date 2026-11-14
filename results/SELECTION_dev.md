# Chọn cấu hình trên dev (ghi ngày 2026-11-14, TRƯỚC khi chạy test)

Model: `claude-haiku-5-5` (Claude API, lớp tương thích OpenAI SDK). Embedding/index: MiniLM 384 chiều, index B Day 6 (356 chunk).
Dev: 15 câu có đáp án + 2 câu thiếu bằng chứng. Test chưa chạy lần nào cho Day 7.

## Retrieval với câu hỏi gốc (không LLM) — `results/retrieval/summary_dev.json`
| Phương pháp | Hit@1 | Evidence Hit@3 | Recall@10 | MRR@10 | ms/câu |
|---|---|---|---|---|---|
| dense (baseline) | 11/15 | 13/15 | 14/15 | 0.80 | 54 |
| lexical BM25 | 12/15 | 12/15 | 14/15 | 0.825 | 15 |
| hybrid RRF | 13/15 | 14/15 | 14/15 | 0.90 | 70 |

## Agent — `results/agent/summary_dev.json`
| Cấu hình | Context Evidence Rate | Từ chối đúng | Từ chối nhầm | Số lần tìm (số câu) | Ký tự context TB | Prompt tokens | Chi phí | s/câu |
|---|---|---|---|---|---|---|---|---|
| A_dense (baseline) | 12/15 | 2/2 | 1/15 | 1 (17) | 1162 | 40 202 | 0.00632 USD | 2.98 |
| B_lexical | 12/15 | 2/2 | 1/15 | 1 (17) | 1125 | 35 974 | 0.00541 USD | 2.81 |
| C_hybrid | 12/15 | 2/2 | 1/15 | 1 (17) | 1138 | 38 707 | 0.00612 USD | 3.02 |
| D_hybrid_multi (cải tiến 1) | 14/15 | 2/2 | 0/15 | 1 (13), 2 (1), 3 (3) | 1350 | 45 016 | 0.00657 USD | 3.21 |
| E_hybrid_multi_nb (cải tiến 2) | **15/15** | 2/2 | 0/15 | 1 (15), 2 (1), 3 (1) | 3312 | 56 549 | 0.00768 USD | 2.87 |

Mọi trích dẫn của mọi cấu hình đều có id nằm trong context (kiểm tra tự động; việc nguồn có hỗ trợ câu trả lời hay không được chấm tay trên test).

## Hai lỗi dev, nguyên nhân và kết quả sau thay đổi
1. **q14 — lệch từ vựng.** Câu hỏi nói "mental shortcuts", đoạn bằng chứng `p42-p00` nói "heuristics" và là phần đuôi của đoạn văn bắt đầu ở trang 41. Câu hỏi gốc không đưa được đoạn này vào top 10 ở cả ba phương pháp. A/B/C tìm một lần rồi **từ chối** (trung thực nhưng là từ chối nhầm).
   Giả thuyết: cho model tìm lại bằng từ khác sẽ tới được đoạn đúng. Kết quả: D tìm 3 lần (câu tìm thứ 3 "heuristics can result in systematic errors…") và lấy được `p42-p00`, trả lời đúng có trích dẫn; E lấy được ở lần tìm thứ 2.
2. **q10 — bằng chứng nằm ở chunk kế bên.** Lần tìm đầu chỉ đưa lên `p37-p09` (câu "Waiting too long…"), còn câu trả lời "vì sao" nằm ở chunk liền sau `p37-p10` (đây cũng là lý do Day 6 tách đoạn evidence 2 câu). A–D không có `p37-p10` trong context nên chỉ trả lời được một phần.
   Giả thuyết: kèm chunk liền trước/sau sẽ đưa phần còn thiếu vào context. Kết quả: E có `p37-p10` (hàng xóm của `p37-p09`) và trả lời đủ ý.
   (q11 cũng được D sửa nhờ lần tìm thứ 2 và được E sửa nhờ hàng xóm `p40-p00`.)

## Tiêu chí và lựa chọn
Tiêu chí (theo GUIDE: retrieval, context, câu trả lời, chi phí/thời gian), áp dụng theo thứ tự:
1. Context Evidence Rate cao nhất; 2. không từ chối nhầm và vẫn từ chối đúng 2/2; 3. chi phí và thời gian chấp nhận được (< 0.001 USD/câu, < 5 s/câu).

**Chọn E_hybrid_multi_nb.** Đây là cấu hình duy nhất có đủ bằng chứng cho 15/15 câu, không từ chối nhầm, vẫn từ chối đúng 2/2.
Đánh đổi: context gấp khoảng 2.5 lần D (3312 so với 1350 ký tự), prompt tokens +26% so với D, chi phí +17% so với D (0.00045 USD/câu), thời gian tương đương vì ít phải tìm lại.

Lưu ý trung thực: tiêu chí trên được viết ra **sau khi đã xem kết quả agent trên dev** (nhưng trước khi chạy bất kỳ câu test nào). Câu tìm do model tự đặt và có thể khác giữa các lần chạy, nên chênh lệch 1 câu giữa các cấu hình là nhỏ.

Test sẽ chạy **một lần** cho baseline `A_dense` và cấu hình chọn `E_hybrid_multi_nb`, cùng retrieval với câu hỏi gốc cho cả ba phương pháp. Không chỉnh hệ thống sau khi xem test.
