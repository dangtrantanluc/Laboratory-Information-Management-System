"""m31: Index cho khoá ngoại.

Postgres KHÔNG tự tạo index cho FK (khác MySQL/InnoDB). 76 cột FK đang thiếu
index → mọi thao tác vô hiệu hoá/xoá user phải seq scan toàn bộ bảng tham chiếu để
kiểm ràng buộc RESTRICT. Hiện tại nhanh vì bảng nhỏ; khi samples lên 200k dòng thì
mỗi thao tác quản trị user khoá bảng vài giây.

Dùng CONCURRENTLY để không khoá bảng khi chạy trên production đang có tải.
"""
from alembic import op

revision: str = "1718870400030"
down_revision: str = "1718870400029"
branch_labels = None
depends_on = None

# Nhóm A — đường truy vấn: những cột thực sự dùng để lọc/join.
_FK_INDEXES_QUERY_PATH = [
    ("customer_info_requests", "decided_by"),
    ("customer_info_requests", "requester_user_id"),
    ("quotation_items", "test_parameter_id"),
    ("staff_activities", "department_id"),
    ("training_certificates", "host_user_id"),
]

# Nhóm B — cột audit (created_by/updated_by/approved_by/...): chỉ ảnh hưởng khi
# xoá hoặc vô hiệu hoá user, lúc Postgres kiểm ON DELETE RESTRICT.
_FK_INDEXES_AUDIT = [
    ("activity_reports", "created_by"),
    ("activity_reports", "reviewed_by"),
    ("capa_actions", "created_by"),
    ("capa", "closed_by"),
    ("capa", "created_by"),
    ("capa", "verified_by"),
    ("chemical_lots", "created_by"),
    ("chemical_lots", "updated_by"),
    ("chemical_recheck_records", "checked_by"),
    ("chemicals", "created_by"),
    ("chemicals", "updated_by"),
    ("community_services", "created_by"),
    ("community_services", "updated_by"),
    ("competences", "created_by"),
    ("competences", "updated_by"),
    ("customers", "created_by"),
    ("customers", "updated_by"),
    ("departments", "created_by"),
    ("departments", "updated_by"),
    ("document_versions", "approved_by"),
    ("document_versions", "reviewed_by"),
    ("document_versions", "submitted_by"),
    ("documents", "created_by"),
    ("documents", "updated_by"),
    ("equipments", "created_by"),
    ("equipments", "updated_by"),
    ("form_submissions", "reviewed_by"),
    ("form_submissions", "submitted_by"),
    ("form_templates", "created_by"),
    ("form_templates", "updated_by"),
    ("hr_profiles", "created_by"),
    ("hr_profiles", "updated_by"),
    ("improvements", "created_by"),
    ("improvements", "updated_by"),
    ("lab_access_cards", "created_by"),
    ("lab_access_cards", "updated_by"),
    ("lab_registrations", "approved_by"),
    ("lab_registrations", "created_by"),
    ("lab_registrations", "updated_by"),
    ("nonconformities", "updated_by"),
    ("publications", "created_by"),
    ("publications", "updated_by"),
    ("quotations", "created_by"),
    ("research_contracts", "created_by"),
    ("research_contracts", "updated_by"),
    ("research_projects", "created_by"),
    ("research_projects", "updated_by"),
    ("risk_treatments", "created_by"),
    ("risks", "closed_by"),
    ("risks", "created_by"),
    ("risks", "updated_by"),
    ("sample_assignments", "created_by"),
    ("sample_assignments", "updated_by"),
    ("sample_intakes", "created_by"),
    ("sample_results", "approved_by"),
    ("sample_results", "entered_by"),
    ("samples", "created_by"),
    ("samples", "updated_by"),
    ("staff_activities", "created_by"),
    ("staff_activities", "updated_by"),
    ("student_mentorships", "created_by"),
    ("student_mentorships", "updated_by"),
    ("teaching_courses", "created_by"),
    ("teaching_courses", "updated_by"),
    ("test_parameters", "created_by"),
    ("test_requests", "created_by"),
    ("test_requests", "updated_by"),
    ("training_certificates", "created_by"),
    ("training_certificates", "updated_by"),
    ("users", "created_by"),
    ("users", "updated_by"),
]

_FK_INDEXES = _FK_INDEXES_QUERY_PATH + _FK_INDEXES_AUDIT


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY KHÔNG chạy được trong transaction → cần autocommit.
    with op.get_context().autocommit_block():
        for table, col in _FK_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_{table}_{col} "
                f"ON {table} ({col})"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table, col in _FK_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS ix_{table}_{col}")
