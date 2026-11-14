# Chọn cấu hình agent (phần nâng cao) trên dev

Dev: 18 câu (15 có đáp án: 3 bảng, 3 ảnh/sơ đồ, 3 biểu đồ, 3 multi-hop, 3 text; 3 thiếu bằng chứng). Cùng model claude-haiku-5-5 (temperature 0), cùng index 844 chunk, cùng câu hỏi. Kết quả: `results/advanced/agent/*_dev.json`, `summary_dev.json`.

| Cấu hình | Tìm trên | Gold đủ trong context | Trích dẫn trúng chunk gold | Số liệu khớp đáp án (TB) | Từ chối đúng | Lỗi | Chi phí 18 câu | s/câu |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| V0_text_only (mốc) | chỉ đoạn văn, hybrid, k=5 | 3/15 | 2/15 | 0.513 | 3/3 | 0 | 0.0282 USD | 6.18 |
| V1_dense | chữ + hình, dense, k=5 | 12/15 | 12/15 | 0.898 | 3/3 | 0 | 0.0274 USD | 4.67 |
| **V2_hybrid** | chữ + hình, hybrid, k=5 | 14/15 | **15/15** | **1.0** | 3/3 | 0 | **0.0189 USD** | **3.82** |
| V3_hybrid_k8 | chữ + hình, hybrid, k=8 | 14/15 | 14/15 | 1.0 | 3/3 | 0 | 0.0243 USD | 4.03 |

"Gold đủ trong context" của V2 là 14/15 vì ở ad12 agent lấy giá trị 2020 (18.8) từ Figure 1.22 thay vì Table 1.1; con số giống nhau và có trích dẫn trang, nên câu trả lời vẫn đúng.

## Đọc từng câu (dev)

Đọc 18 câu trả lời của V2 và V3, đối chiếu với đáp án và evidence trong benchmark:
- V2_hybrid: 15/15 câu có đáp án trả lời đúng và đủ, đúng đơn vị/năm/điều kiện, trích dẫn chunk chứa evidence kèm tên bảng/hình và trang PDF; 3/3 câu thiếu bằng chứng từ chối, không bịa số.
- V3_hybrid_k8: cũng 15/15 và 3/3; ở ad14 trích dẫn ghi dạng `[pea-p189-t01, PDF page 189]` nên bộ đếm tự động không nhận (lỗi định dạng, nội dung đúng).
- V0_text_only: thiếu nội dung bảng/hình nên phần lớn câu bảng/biểu đồ/sơ đồ không có số đúng, cho thấy index hình là cần thiết.

Lưu ý khi đọc dev: các câu từ chối đôi khi nêu thêm thông tin gần đúng có trích dẫn (vd. ad16 nêu "lương tối thiểu khoảng 4 triệu VND/tháng" từ trang 67 và 188, nhưng nói rõ không có số theo vùng). Đây là thông tin có trong tài liệu, không phải khẳng định thiếu căn cứ.

## Tiêu chí chọn (viết sau khi xem dev, trước khi chạy test)

1. Đúng nhiều nhất khi đọc từng câu dev (cả câu có đáp án lẫn từ chối).
2. Nếu bằng nhau: trích dẫn trúng chunk gold nhiều hơn.
3. Nếu vẫn bằng nhau: chi phí và thời gian thấp hơn.

**Chốt: V2_hybrid** (hybrid RRF trên chunk chữ + hình, top_k 5, tối đa 4 lần tìm, budget 24.000 ký tự). V2 và V3 bằng nhau ở tiêu chí 1; V2 hơn ở tiêu chí 2 và 3.

## Thay đổi benchmark sau dev, trước test

- at30 (test): thay câu "gross tertiary enrollment rate 2020" bằng "poverty rate of Lao PDR". Khi rà lại phần dò từ khóa với mẫu rộng hơn, thấy báo cáo có biểu đồ tỷ lệ đi học theo tuổi (Figure 4.6, 4.9), câu cũ dễ gây tranh cãi khi chấm. Việc thay câu dựa trên nội dung tài liệu, không dựa trên kết quả agent (test chưa chạy).
- ad16 (dev): sửa ghi chú cách kiểm tra (bản đầu bỏ sót cụm "minimum monthly wages"); câu hỏi không đổi.

Lệnh chạy test (một lần): `python -X utf8 -m src.adv_agent --split test --configs V2_hybrid`
- Bộ đọc trích dẫn trong `src/adv_agent.py` được sửa để nhận cả dạng `[id, PDF page n]` và `[id1, id2]` (lỗi thấy ở V3 ad14). Chỉ ảnh hưởng chỉ số tự động, không đổi hành vi agent; số liệu dev ở bảng trên là theo bộ đọc cũ.
