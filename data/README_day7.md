# Dữ liệu và benchmark Day 7

Tạo lại bằng `python scripts/export_day6.py` (cần database Day 6 đang chạy và repo Day 6 nằm cạnh repo này).

## Corpus: `chunks.json`
- 356 chunk của **index B** Day 6 (chia theo đoạn văn, tối đa 500 ký tự), xuất thẳng từ bảng `chunks` trong pgvector Day 6. Day 7 dùng lại đúng các vector đã lưu, không tạo index mới.
- Nguồn: *Principles of Management*, OpenStax, ©2026 Rice University, CC BY-NC-SA 4.0, chương 1–2, trang PDF 21–63 (41 trang nội dung). Access for free at openstax.org. Dùng cho mục đích học tập phi thương mại, chia sẻ lại cùng giấy phép.
- Trường: `id`, `text`, `source_id`, `source`, `page` (trang PDF sách gốc), `metadata` gồm `chapter`, `printed_page`, `char_start`, `char_end`, `day6_index`, `embedding_model`, `content_hash`.

## Câu hỏi: `questions.json`
| | Có đáp án | Thiếu bằng chứng |
|---|---:|---:|
| dev | 15 | 2 (u01, u02) |
| test | 5 | 2 (u03, u04) |

- 20 câu có đáp án lấy nguyên từ benchmark Day 6, giữ nguyên split. Tập test Day 6 chỉ chạy một lần sau khi đã chốt cấu hình và không dùng để chỉnh hệ thống; ở Day 7 mọi lựa chọn cũng chỉ dựa trên dev.
- `gold`: danh sách evidence thay thế `{source_id, page, evidence}`; mỗi evidence nằm trọn trong một chunk đúng nguồn và trang (script kiểm tra và ghi `chunk_ids` để người chấm tra cứu).
- `filter`: phạm vi chương mà **người dùng nêu trong câu hỏi** (q07, q08, q18, q20). Không phải gold.
- **Thay đổi so với Day 6:** q10 dùng câu thứ hai của đoạn evidence cũ (trường `day6_evidence` giữ bản cũ), vì đoạn 2 câu vắt qua hai chunk B (`p37-p09` | `p37-p10`) nên không thể nằm trọn trong một chunk. Câu thứ hai một mình đủ trả lời câu hỏi "vì sao".
- 4 câu thiếu bằng chứng (`unanswerable.json`) gần chủ đề sách; cách kiểm tra vắng mặt ghi ở `absence_reason` (tìm từ khóa trên toàn bộ 41 trang, không chỉ dựa vào top-k).

`gold`, `expected_answer`, `chunk_ids`, `absence_reason` không bao giờ được đưa vào agent hay retrieval.
