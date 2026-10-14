"""m54: Báo cáo mẫu phân tích theo quý — các phòng lab nhập, Văn phòng tổng hợp.

VẤN ĐỀ
Cuối mỗi quý Văn phòng cần một bảng "STT · Mã số mẫu · Loại mẫu · Số lượng · Chỉ tiêu
phân tích · Phòng nghiên cứu phụ trách" cho toàn Viện. Mẫu hiện được nhận và đánh mã
NGOÀI hệ thống (mã dạng 26N265), nên luồng Nhận & Chuyển mẫu chưa sinh được bảng này:
các lab tự nhập, trưởng lab/KTV nộp, Văn phòng trả lại hoặc chốt rồi xuất Excel.

BA BẢNG
- quarterly_sample_reports: báo cáo của MỘT phòng lab trong MỘT quý — duy nhất theo (phòng, năm, quý).
  Trạng thái draft → submitted → (returned ↔ submitted) → locked; mở khoá đưa về returned.
- quarterly_sample_items: mỗi dòng Excel. KHÔNG unique theo mã mẫu: một mẫu được chia chỉ
  tiêu cho nhiều phòng (đã xác nhận với nghiệp vụ), và cùng phòng có thể nhận nhiều đợt.
- quarterly_sample_item_criteria: chỉ tiêu chọn từ danh mục. Lưu cả test_parameter_id (để
  thống kê) lẫn TÊN tại thời điểm nhập — danh mục đổi tên về sau không được làm đổi báo
  cáo đã chốt. Chỉ tiêu ngoài danh mục nằm ở cột extra_criteria của dòng.
"""
from alembic import op

revision: str = "1718870400053"
down_revision: str = "1718870400052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE quarterly_sample_reports (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            department_id  UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            year           SMALLINT NOT NULL,
            quarter        SMALLINT NOT NULL,
            status         VARCHAR(12) NOT NULL DEFAULT 'draft',
            lab_note       TEXT,
            submitted_by   UUID REFERENCES users(id) ON DELETE RESTRICT,
            submitted_at   TIMESTAMPTZ,
            returned_by    UUID REFERENCES users(id) ON DELETE RESTRICT,
            returned_at    TIMESTAMPTZ,
            return_reason  TEXT,
            locked_by      UUID REFERENCES users(id) ON DELETE RESTRICT,
            locked_at      TIMESTAMPTZ,
            created_by     UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_sample_report_period UNIQUE (department_id, year, quarter),
            CONSTRAINT ck_sample_report_quarter CHECK (quarter BETWEEN 1 AND 4),
            CONSTRAINT ck_sample_report_year CHECK (year BETWEEN 2000 AND 2100),
            CONSTRAINT ck_sample_report_status
                CHECK (status IN ('draft','submitted','returned','locked'))
        );
        CREATE INDEX idx_sample_reports_period ON quarterly_sample_reports(year, quarter);

        CREATE TABLE quarterly_sample_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            report_id       UUID NOT NULL REFERENCES quarterly_sample_reports(id) ON DELETE CASCADE,
            sample_code     VARCHAR(50) NOT NULL,
            received_date   DATE NOT NULL,
            matrix          VARCHAR(24) NOT NULL,
            matrix_other    VARCHAR(255),
            quantity        INTEGER NOT NULL,
            extra_criteria  TEXT,
            note            TEXT,
            created_by      UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by      UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_sri_quantity CHECK (quantity >= 1),
            CONSTRAINT ck_sri_matrix CHECK (matrix IN
                ('soil','water','fertilizer','feed','food','quarantine','molecular','other')),
            CONSTRAINT ck_sri_matrix_other CHECK (matrix <> 'other' OR matrix_other IS NOT NULL)
        );
        CREATE INDEX idx_sri_report ON quarterly_sample_items(report_id);
        CREATE INDEX idx_sri_sample_code ON quarterly_sample_items(sample_code);

        CREATE TABLE quarterly_sample_item_criteria (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id            UUID NOT NULL REFERENCES quarterly_sample_items(id) ON DELETE CASCADE,
            test_parameter_id  UUID REFERENCES test_parameters(id) ON DELETE SET NULL,
            name               VARCHAR(500) NOT NULL,
            sort_order         SMALLINT NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_sric_item ON quarterly_sample_item_criteria(item_id);
        CREATE INDEX idx_sric_param ON quarterly_sample_item_criteria(test_parameter_id);
        """
    )

    # RBAC — lab (staff + trưởng lab) nhập và nộp báo cáo của PHÒNG MÌNH; Văn phòng và
    # admin xem toàn Viện, trả lại / chốt / mở khoá, xuất Excel; Ban lãnh đạo chỉ xem.
    op.execute(
        """
        INSERT INTO permissions (resource, action, description) VALUES
            ('quarterly_sample_report','read','Xem báo cáo mẫu phân tích theo quý'),
            ('quarterly_sample_report','write','Nhập và nộp báo cáo mẫu của phòng mình'),
            ('quarterly_sample_report','review','Trả lại / chốt / mở khoá báo cáo mẫu, xuất Excel')
        ON CONFLICT (resource, action) DO NOTHING;

        INSERT INTO roles_permissions (role, resource, action, scope) VALUES
            ('staff','quarterly_sample_report','read','department'),
            ('staff','quarterly_sample_report','write','department'),
            ('lab_manager','quarterly_sample_report','read','department'),
            ('lab_manager','quarterly_sample_report','write','department'),
            ('office','quarterly_sample_report','read','all'),
            ('office','quarterly_sample_report','review','all'),
            ('admin','quarterly_sample_report','read','all'),
            ('admin','quarterly_sample_report','review','all'),
            ('leader','quarterly_sample_report','read','all')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource = 'quarterly_sample_report';")
    op.execute("DELETE FROM permissions WHERE resource = 'quarterly_sample_report';")
    op.execute("DROP TABLE IF EXISTS quarterly_sample_item_criteria;")
    op.execute("DROP TABLE IF EXISTS quarterly_sample_items;")
    op.execute("DROP TABLE IF EXISTS quarterly_sample_reports;")
