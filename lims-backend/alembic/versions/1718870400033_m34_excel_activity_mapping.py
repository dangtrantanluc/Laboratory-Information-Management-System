"""M34 — map trọn vẹn file "TỔNG HỢP CÁC HOẠT ĐỘNG NĂM 2024-2025" vào schema.

Gom mọi cột còn thiếu vào MỘT migration để chỉ khoá bảng một lần trên production.

Ba nhóm thay đổi:
  1. evidence_url — cột "Link minh chứng" có mặt ở 8/11 bảng của file Excel nhưng
     không tồn tại ở bất kỳ bảng nào. `attachments` là tệp upload, KHÔNG thay thế
     được đường dẫn ngoài (Google Drive, DOI, trang tạp chí, ảnh khen thưởng).
  2. Bốn trường phân loại mà Excel diễn đạt bằng TIÊU ĐỀ NHÓM thay vì cột, nên
     vô hình nếu chỉ đọc dòng header:
       - publications.patent_kind   ← mục I/II/III: sáng chế · GPHI · giống cây trồng
       - teaching_courses.training_level ← hai bảng Đại học / Sau đại học
       - training_certificates.cert_kind ← lớp ngắn hạn / tập huấn an toàn PTN
       - research_contracts.contract_no  ← cột D "Số hợp đồng" (kèm signed_date vì
         Excel gộp "PUR.2024.00618 ký ngày 23/9/2024" vào một ô)
  3. Học kỳ 3 (yêu cầu nghiệp vụ mới) — hk3_theory_hours / hk3_practice_hours,
     đối xứng với hai cặp HK1/HK2 đã có.

Tất cả cột đều NULL-able, không backfill: dữ liệu cũ hợp lệ nguyên trạng.
"""
from alembic import op

revision: str = "1718870400033"
down_revision: str = "1718870400032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===== 1. Link minh chứng =====
    op.execute("ALTER TABLE research_projects     ADD COLUMN IF NOT EXISTS evidence_url TEXT;")
    op.execute("ALTER TABLE publications          ADD COLUMN IF NOT EXISTS evidence_url TEXT;")
    op.execute("ALTER TABLE research_contracts    ADD COLUMN IF NOT EXISTS evidence_url TEXT;")
    op.execute("ALTER TABLE teaching_courses      ADD COLUMN IF NOT EXISTS evidence_url TEXT;")
    op.execute("ALTER TABLE staff_activities      ADD COLUMN IF NOT EXISTS evidence_url TEXT;")
    op.execute("ALTER TABLE community_services    ADD COLUMN IF NOT EXISTS evidence_url TEXT;")

    # ===== 2. Trường phân loại ẩn trong tiêu đề nhóm của Excel =====
    op.execute("ALTER TABLE publications          ADD COLUMN IF NOT EXISTS patent_kind VARCHAR(24);")
    op.execute("ALTER TABLE research_contracts    ADD COLUMN IF NOT EXISTS contract_no VARCHAR(128);")
    op.execute("ALTER TABLE research_contracts    ADD COLUMN IF NOT EXISTS signed_date DATE;")
    op.execute("ALTER TABLE teaching_courses      ADD COLUMN IF NOT EXISTS training_level VARCHAR(16);")
    op.execute("ALTER TABLE training_certificates ADD COLUMN IF NOT EXISTS cert_kind VARCHAR(24);")

    # ===== 3. Học kỳ 3 =====
    op.execute("ALTER TABLE teaching_courses ADD COLUMN IF NOT EXISTS hk3_theory_hours   SMALLINT;")
    op.execute("ALTER TABLE teaching_courses ADD COLUMN IF NOT EXISTS hk3_practice_hours SMALLINT;")

    # ===== CHECK constraint cho 3 trường phân loại =====
    # patent_kind chỉ có nghĩa khi type='patent'; NULL luôn hợp lệ để bản ghi cũ không vỡ.
    op.execute(
        """
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_patent_kind;
        ALTER TABLE publications ADD CONSTRAINT ck_pub_patent_kind CHECK (
            patent_kind IS NULL
            OR (type = 'patent'
                AND patent_kind IN ('invention', 'utility_solution', 'plant_variety'))
        );
        """
    )
    op.execute(
        """
        ALTER TABLE teaching_courses DROP CONSTRAINT IF EXISTS ck_tc_training_level;
        ALTER TABLE teaching_courses ADD CONSTRAINT ck_tc_training_level CHECK (
            training_level IS NULL
            OR training_level IN ('undergraduate', 'postgraduate')
        );
        """
    )
    op.execute(
        """
        ALTER TABLE training_certificates DROP CONSTRAINT IF EXISTS ck_cert_kind;
        ALTER TABLE training_certificates ADD CONSTRAINT ck_cert_kind CHECK (
            cert_kind IS NULL
            OR cert_kind IN ('short_course', 'lab_safety')
        );
        """
    )
    # Số tiết HK3: cùng biên với HK1/HK2 ở tầng schema (0..10000).
    op.execute(
        """
        ALTER TABLE teaching_courses DROP CONSTRAINT IF EXISTS ck_tc_hk3_hours;
        ALTER TABLE teaching_courses ADD CONSTRAINT ck_tc_hk3_hours CHECK (
            (hk3_theory_hours   IS NULL OR hk3_theory_hours   >= 0)
            AND (hk3_practice_hours IS NULL OR hk3_practice_hours >= 0)
        );
        """
    )

    # ===== Danh mục cấp đề tài: bổ sung mã còn thiếu so với dữ liệu 2024-2025 =====
    # Dòng 13 của sheet NCKH ghi cấp là "Chương trình Mô hình giảm nghèo thuộc Chương
    # trình mục tiêu quốc gia giảm nghèo bền vững giai đoạn 2021-2025, Bộ GD&ĐT" —
    # không khớp mã nào trong 6 mã seed ban đầu và dài hơn VARCHAR(32) của cột code.
    op.execute(
        """
        INSERT INTO research_project_levels (code, label, sort_order) VALUES
            ('national_program', 'Chương trình mục tiêu quốc gia', 7),
            ('other',            'Khác',                          99)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ===== Index phục vụ lọc theo phân loại mới =====
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tc_training_level ON teaching_courses (training_level) "
        "WHERE training_level IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cert_kind ON training_certificates (cert_kind) "
        "WHERE cert_kind IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pub_patent_kind ON publications (patent_kind) "
        "WHERE patent_kind IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pub_patent_kind;")
    op.execute("DROP INDEX IF EXISTS ix_cert_kind;")
    op.execute("DROP INDEX IF EXISTS ix_tc_training_level;")

    op.execute("ALTER TABLE publications          DROP CONSTRAINT IF EXISTS ck_pub_patent_kind;")
    op.execute("ALTER TABLE teaching_courses      DROP CONSTRAINT IF EXISTS ck_tc_training_level;")
    op.execute("ALTER TABLE teaching_courses      DROP CONSTRAINT IF EXISTS ck_tc_hk3_hours;")
    op.execute("ALTER TABLE training_certificates DROP CONSTRAINT IF EXISTS ck_cert_kind;")

    op.execute("ALTER TABLE teaching_courses      DROP COLUMN IF EXISTS hk3_practice_hours;")
    op.execute("ALTER TABLE teaching_courses      DROP COLUMN IF EXISTS hk3_theory_hours;")
    op.execute("ALTER TABLE training_certificates DROP COLUMN IF EXISTS cert_kind;")
    op.execute("ALTER TABLE teaching_courses      DROP COLUMN IF EXISTS training_level;")
    op.execute("ALTER TABLE research_contracts    DROP COLUMN IF EXISTS signed_date;")
    op.execute("ALTER TABLE research_contracts    DROP COLUMN IF EXISTS contract_no;")
    op.execute("ALTER TABLE publications          DROP COLUMN IF EXISTS patent_kind;")

    op.execute("ALTER TABLE community_services    DROP COLUMN IF EXISTS evidence_url;")
    op.execute("ALTER TABLE staff_activities      DROP COLUMN IF EXISTS evidence_url;")
    op.execute("ALTER TABLE teaching_courses      DROP COLUMN IF EXISTS evidence_url;")
    op.execute("ALTER TABLE research_contracts    DROP COLUMN IF EXISTS evidence_url;")
    op.execute("ALTER TABLE publications          DROP COLUMN IF EXISTS evidence_url;")
    op.execute("ALTER TABLE research_projects     DROP COLUMN IF EXISTS evidence_url;")

    # KHÔNG xoá mã danh mục đã seed: có thể đang được tham chiếu bởi research_projects.
