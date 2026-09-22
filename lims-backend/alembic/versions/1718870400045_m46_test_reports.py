"""m46: PHÁT HÀNH KẾT QUẢ THỬ NGHIỆM (BM 7.8/01/RIBE) bằng cách tải tệp lên.

VẤN ĐỀ
Phiếu nhận mẫu có bước cuối `completed` mang nhãn "Đã trả kết quả", nhưng chuyển sang
bước đó chỉ ghi một chuỗi ký tự vào cột `status`. Không có tệp, không có số hiệu, không
có ngày phát hành, không biết ai ký và ai đã gửi cho khách. Khi khách khiếu nại "kết quả
anh gửi tháng trước ghi pH 6,12", hệ thống không có gì để đối chiếu.

Nút "Xuất phiếu kết quả (PDF)" ở frontend dựng BM 7.8/01 ngay trên trình duyệt từ các ô
`ket_qua`/`don_vi`/`phuong_phap` của phiếu chuyển — nhưng bản in đó KHÔNG được lưu lại:
in xong là mất, và nếu dữ liệu phía sau đổi thì hai người in hai lúc cầm hai tờ khác
nhau, cùng mang chữ ký Viện trưởng.

Đây đúng là bước 11 "Phát hành" mà docs/VILAB-business-flow-audit.html liệt là mắt xích
còn trống của luồng nghiệp vụ.

VÌ SAO TẢI TỆP LÊN CHỨ KHÔNG SINH TỆP
Biểu mẫu thật (xem docs/26N323 - … NHÂN ÁI.docx) là BỐN phiếu con trong một tệp, mỗi
khối một mã mẫu (88/VNB-BMLS-1-4/18, 5-8/18, 9-10/18, 11-14/18), cột kết quả tách theo
từng mẫu con có tên riêng ("Suối bản", "A Đa – Đất vàng"), khối 1 là mẫu nước còn khối 4
là mẫu đất với bộ chỉ tiêu hoàn toàn khác, kèm chú thích LOQ/LOD/KPH theo từng khối.

Mô hình hiện tại chỉ có MỘT ô text `ket_qua` cho MỘT chỉ tiêu — không diễn tả nổi ma
trận đó. Sinh tệp tự động đòi mô hình hoá thêm mẫu con, ma trận kết quả, giới hạn phát
hiện theo phương pháp: một dự án riêng, và nó chặn việc đóng lỗ hổng này thêm nhiều
tháng. Đánh đổi được chấp nhận có ý thức: hệ thống biết ĐÃ PHÁT HÀNH PHIẾU NÀO, LÚC NÀO,
CHO AI — không biết trong phiếu ghi gì.

VÌ SAO BẢNG RIÊNG CHỨ KHÔNG CHỈ THÊM MỘT owner_type
`attachments` trả lời được "có tệp gì". Chứng từ phát hành phải trả lời thêm: số hiệu là
gì, phát hành ngày nào (mốc tính 7 ngày lưu mẫu ghi ở chân biểu mẫu, và mốc tính trả
đúng hay trễ hạn), ai phát hành, bản gốc hay bản sửa đổi thứ mấy và vì sao, đã gửi khách
chưa, đã thu hồi chưa. Nhét từng ấy vào tên tệp là cách chắc chắn nhất để sáu tháng sau
không ai trả lời được.

QUYỀN MỚI, KHÔNG TÁI DÙNG `intake:read`
`intake:read` đang được cấp cho staff và lab_manager với scope 'all'. Dùng lại nó để gác
tệp kết quả là mở toàn bộ PII khách hàng cho khối lab đang bị che bởi m26 — tệp BM 7.8/01
chứa nguyên văn tên và địa chỉ khách ở ngay bảng đầu phiếu. Đúng loại đường vòng mà đợt
vá `attachment_authz` vừa bịt.

Phạm vi đã chốt với chủ nghiệp vụ: ĐÚNG BA VAI — reception, leader, admin.

⚠ TRIỂN KHAI — BẮT BUỘC XÓA CACHE RBAC SAU KHI CHẠY
`roles_permissions` được cache Redis TTL 300s và `core/rbac.invalidate_role_cache()`
không được gọi tự động ở đâu cả. Chạy migration xong mà không xoá cache thì quyền mới
chưa có hiệu lực trong tối đa 5 phút, và người kiểm thử sẽ báo "bấm vào bị 403" đúng lúc
mọi thứ thật ra đã đúng. Xem README §Triển khai.
"""
from alembic import op
from sqlalchemy import text

revision: str = "1718870400045"
down_revision: str = "1718870400044"
branch_labels = None
depends_on = None

# Danh sách owner_type SAU migration này. Giữ khớp Attachment.VALID_OWNER_TYPES —
# hai nơi lệch nhau thì model cho phép ghi giá trị mà DB từ chối, và lỗi hiện ra dưới
# dạng IntegrityError 500 chứ không phải thông báo nghiệp vụ.
_OWNER_TYPES = ", ".join(
    f"'{t}'"
    for t in (
        "test_request", "sample", "sample_result", "chemical", "chem_lot",
        "document", "document_version", "equipment", "calibration", "hr_profile",
        "publication", "form_template", "form_submission", "sample_intake",
        "sample_dispatch", "research_project", "research_contract", "teaching_course",
        "staff_activity", "training_certificate",
        "test_report",  # m46
    )
)


def upgrade() -> None:
    conn = op.get_bind()

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS test_reports (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            -- RESTRICT, không CASCADE: chứng từ đã trao khách không được biến mất
            -- vì ai đó xoá phiếu nhận mẫu.
            intake_id        UUID NOT NULL REFERENCES sample_intakes(id) ON DELETE RESTRICT,
            report_no        VARCHAR(64) NOT NULL,
            version          INTEGER NOT NULL DEFAULT 1,
            -- Bản mà nó thay thế. SET NULL: mất liên kết còn hơn mất bản ghi.
            supersedes_id    UUID NULL REFERENCES test_reports(id) ON DELETE SET NULL,
            revision_reason  TEXT NULL,
            status           VARCHAR(16) NOT NULL DEFAULT 'draft',
            title            VARCHAR(255) NULL,
            note             TEXT NULL,
            issued_at        DATE NULL,
            issued_by        UUID NULL REFERENCES users(id) ON DELETE RESTRICT,
            delivered_at     TIMESTAMPTZ NULL,
            delivery_method  VARCHAR(20) NULL,
            delivered_to     VARCHAR(255) NULL,
            delivery_note    TEXT NULL,
            revoked_at       TIMESTAMPTZ NULL,
            revoked_by       UUID NULL REFERENCES users(id) ON DELETE RESTRICT,
            revoked_reason   TEXT NULL,
            deleted_at       TIMESTAMPTZ NULL,
            created_by       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            updated_by       UUID NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT ck_tr_status
                CHECK (status IN ('draft','issued','delivered','revoked')),
            CONSTRAINT ck_tr_version CHECK (version >= 1),
            -- Sao khuôn ck_res_revision_reason của sample_results: sửa một bản đã phát
            -- hành mà không nêu lý do thì hồ sơ không giải trình được.
            CONSTRAINT ck_tr_revision_reason
                CHECK (version = 1
                       OR (revision_reason IS NOT NULL
                           AND length(btrim(revision_reason)) > 0)),
            -- Rời 'draft' là đã phát hành → phải có ngày và người phát hành. Ba trạng
            -- thái còn lại đều nằm SAU khi phát hành nên cùng chịu ràng buộc này.
            CONSTRAINT ck_tr_issued_pair
                CHECK (status = 'draft'
                       OR (issued_at IS NOT NULL AND issued_by IS NOT NULL)),
            CONSTRAINT ck_tr_delivered
                CHECK (status <> 'delivered' OR delivered_at IS NOT NULL),
            CONSTRAINT ck_tr_revoked
                CHECK (status <> 'revoked'
                       OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
                           AND revoked_reason IS NOT NULL
                           AND length(btrim(revoked_reason)) > 0)),
            -- Khớp bộ giá trị return_method đã có trên phiếu nhận mẫu.
            CONSTRAINT ck_tr_delivery_method
                CHECK (delivery_method IS NULL
                       OR delivery_method IN ('direct','mail','email'))
        );
        """
    )

    # Số hiệu duy nhất, nhưng CHỈ trong các bản còn sống: xoá một bản nháp phải trả lại
    # số hiệu cho lần lập sau, nếu không nhân viên gõ nhầm một lần là mất số vĩnh viễn.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tr_report_no
            ON test_reports(report_no) WHERE deleted_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_tr_intake
            ON test_reports(intake_id) WHERE deleted_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_tr_supersedes ON test_reports(supersedes_id);
        -- Phục vụ BR-08 (chặn chuyển phiếu sang 'completed' khi chưa phát hành) —
        -- truy vấn "phiếu này có chứng từ issued/delivered nào chưa" chạy mỗi lần
        -- đổi trạng thái phiếu.
        CREATE INDEX IF NOT EXISTS idx_tr_intake_status
            ON test_reports(intake_id, status) WHERE deleted_at IS NULL;
        """
    )

    # Nới owner_type của attachments — tệp phiếu kết quả đi qua hạ tầng dùng chung.
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS attachments_owner_type_check;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    op.execute(
        f"ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type "
        f"CHECK (owner_type IN ({_OWNER_TYPES}));"
    )

    # RBAC — danh mục quyền TRƯỚC, vì roles_permissions có FK (resource, action)
    # tới permissions; chèn ngược thứ tự sẽ nổ ForeignKeyViolation giữa migration.
    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('test_report','read',
                 'Xem và tải phiếu kết quả thử nghiệm đã phát hành (BM 7.8/01)'),
                ('test_report','manage',
                 'Tải lên, phát hành, ghi nhận đã gửi khách và thu hồi phiếu kết quả')
            ON CONFLICT (resource, action) DO NOTHING;
            """
        )
    )
    # Đúng ba vai đã chốt. qms và lab_manager CỐ Ý không có mặt: qms xin hồ sơ qua
    # Phòng nhận mẫu như hiện nay, còn Trưởng PTN ký ô "Trưởng PTN/QLKT" ngoài hệ
    # thống. Hệ quả có lợi: không cần cơ chế che tên tệp (tên tệp gốc là
    # "26N323 - CÔNG TY…", tức chính là PII khách hàng).
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','test_report','read','all'),
                ('admin','test_report','manage','all'),
                ('leader','test_report','read','all'),
                ('leader','test_report','manage','all'),
                ('reception','test_report','read','all'),
                ('reception','test_report','manage','all')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource = 'test_report';")
    op.execute("DELETE FROM permissions WHERE resource = 'test_report';")
    # Tệp trước: attachments.owner_id không có FK cứng nên xoá bảng không dọn giúp.
    op.execute("DELETE FROM attachments WHERE owner_type = 'test_report';")
    op.execute("DROP TABLE IF EXISTS test_reports CASCADE;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    _prev = _OWNER_TYPES.replace(", 'test_report'", "")
    op.execute(
        f"ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type "
        f"CHECK (owner_type IN ({_prev}));"
    )
