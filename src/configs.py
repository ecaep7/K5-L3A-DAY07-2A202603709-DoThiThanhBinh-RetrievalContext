"""Các cấu hình agent được so sánh trên dev. Mọi cấu hình dùng cùng model, corpus, câu hỏi và nhãn.

method        : cách truy xuất cho công cụ search_documents (dense / lexical / hybrid)
top_k         : số chunk mỗi lần tìm
max_searches  : số lần tìm tối đa cho một câu hỏi (1 = tìm một lần bằng câu do model tự đặt)
neighbors     : kèm thêm chunk liền trước và liền sau của mỗi kết quả (cùng thứ tự trong sách)
budget_chars  : giới hạn tổng số ký tự text tài liệu đưa vào context; chunk vượt giới hạn bị bỏ và ghi lại
"""
CONFIGS = {
    "A_dense":          {"method": "dense",   "top_k": 3, "max_searches": 1, "neighbors": False, "budget_chars": 6000},
    "B_lexical":        {"method": "lexical", "top_k": 3, "max_searches": 1, "neighbors": False, "budget_chars": 6000},
    "C_hybrid":         {"method": "hybrid",  "top_k": 3, "max_searches": 1, "neighbors": False, "budget_chars": 6000},
    "D_hybrid_multi":   {"method": "hybrid",  "top_k": 3, "max_searches": 3, "neighbors": False, "budget_chars": 6000},
    "E_hybrid_multi_nb": {"method": "hybrid", "top_k": 3, "max_searches": 3, "neighbors": True,  "budget_chars": 9000},
}
BASELINE = "A_dense"
