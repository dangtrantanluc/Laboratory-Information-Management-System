"""MẶT TIỀN TƯƠNG THÍCH — nội dung thật nằm ở `app/services/research/` (M-03/T1.1).

File này từng dài 1.736 dòng và chứa 9 domain tách biệt. Nó đã được tách thành
package `app.services.research`; module này chỉ còn re-export để mọi lời gọi
`research_service.X(...)` hiện có tiếp tục chạy trong lúc chuyển đổi.

KHÔNG thêm code mới vào đây. Viết vào module con tương ứng trong `research/`.

Mặt tiền này sẽ bị xoá khi toàn bộ caller đã chuyển sang import package trực
tiếp — xem MAINTAINABILITY_PLAN.md §T1.1.
"""
from app.services.research import *  # noqa: F401,F403
