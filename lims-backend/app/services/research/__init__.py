"""Package research — tách từ research_service.py (M-03/T1.1).

File gốc dài 1.736 dòng và chứa 9 domain tách biệt: đề tài, bài báo/sáng chế,
hướng dẫn sinh viên, đăng ký lab, giảng dạy, phục vụ cộng đồng, hồ sơ năng lực,
thống kê. Chính tác giả đã đánh dấu ranh giới bằng comment `# ===== X =====`,
nghĩa là ranh giới module đã tồn tại trong đầu người viết, chỉ chưa thành file.
Khi nhiều người sửa nhiều domain thì đó là một điểm conflict merge liên tục.

Việc tách là CƠ HỌC: không đổi logic, không đổi chữ ký hàm.

    _shared               58   competence_service   112
    stats_service        176   community_service    179
    registration_service 187   mentorship_service   191
    teaching_service     201   project_service      354
    publication_service  410

CỐ Ý KHÔNG re-export gì ở đây. Caller import thẳng module domain:

    from app.services.research import project_service
    project_service.list_projects(...)

Gom tất cả vào một namespace bằng `import *` sẽ tái lập đúng vấn đề vừa gỡ:
đọc lời gọi không biết nó thuộc domain nào.

Đồ thị phụ thuộc là hình sao, không có vòng:
    _shared ← project_service, publication_service
"""
