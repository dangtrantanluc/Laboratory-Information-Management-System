"""Package research — tách từ research_service.py (M-03/T1.1).

File gốc dài 1.736 dòng và chứa 9 domain tách biệt: đề tài, bài báo, hướng dẫn
sinh viên, đăng ký lab, giảng dạy, phục vụ cộng đồng, hồ sơ năng lực, thống kê.
Chính tác giả đã đánh dấu ranh giới bằng comment `# ===== X =====`, nghĩa là
ranh giới module đã tồn tại trong đầu người viết, chỉ chưa thành file. Khi nhiều
người sửa nhiều domain thì đó là một file conflict merge liên tục.

Việc tách là CƠ HỌC: không đổi logic, không đổi chữ ký hàm.

`__init__` re-export toàn bộ hàm public để mọi lời gọi cũ
(`research_service.list_projects(...)`) tiếp tục chạy nguyên vẹn. Router chưa
cần sửa dòng nào.

Đồ thị phụ thuộc là hình sao, không có vòng:
    _shared ← project_service, publication_service
"""
from app.services.research.community_service import *  # noqa: F401,F403
from app.services.research.competence_service import *  # noqa: F401,F403
from app.services.research.mentorship_service import *  # noqa: F401,F403
from app.services.research.project_service import *  # noqa: F401,F403
from app.services.research.publication_service import *  # noqa: F401,F403
from app.services.research.registration_service import *  # noqa: F401,F403
from app.services.research.stats_service import *  # noqa: F401,F403
from app.services.research.teaching_service import *  # noqa: F401,F403
