"""m48: hồ sơ nhân sự ĐỨNG ĐỘC LẬP với tài khoản đăng nhập.

VẤN ĐỀ
`hr_profiles` lấy `user_id` vừa làm khoá chính vừa làm khoá ngoại sang `users`. Lược đồ
đó phát biểu rằng "một hồ sơ nhân sự CHÍNH LÀ một tài khoản" — và điều đó không đúng với
thực tế của Viện:

  · Danh sách CBVC-NLĐ 2026 có 33 người, chỉ 6 người đang có tài khoản.
  · Người làm ở Viện không nhất thiết cần đăng nhập phần mềm (nhân viên phục vụ, cán bộ
    mới, người sắp nghỉ).
  · Ngược lại, tài khoản có thể tồn tại trước khi có hồ sơ nhân sự.

Hệ quả trước m48: muốn ghi một người vào sổ nhân sự thì buộc phải tạo cho họ một lối
đăng nhập, kèm email bịa ra và mật khẩu. Đó là lý do đợt nhập danh sách 2026 phải dừng.

NGƯỜI và TÀI KHOẢN là hai thứ có vòng đời riêng
Sau migration này `hr_profiles` mô tả CON NGƯỜI (tên, năm sinh, ngạch, diện hợp đồng),
còn `users` mô tả LỐI VÀO PHẦN MỀM. Chúng nối với nhau bằng `user_id` tuỳ chọn:

    user_id IS NULL      → người có trong sổ nhân sự, chưa có tài khoản
    user_id = <uuid>     → đã gắn; UNIQUE nên một tài khoản chỉ thuộc một hồ sơ

KHÔNG TỰ ĐỘNG GẮN THEO TÊN
Ràng buộc chỉ bảo đảm quan hệ một-một; việc GẮN là thao tác có người xác nhận. Trùng
họ tên là chuyện bình thường ở Việt Nam, nên gắn tự động theo tên sẽ âm thầm nối hồ sơ
lương của người này vào tài khoản của người khác. Tầng ứng dụng chỉ GỢI Ý hồ sơ trùng
tên khi tạo/duyệt tài khoản, và người duyệt bấm xác nhận.

BA BẢNG CON ĐỔI KHOÁ THEO
`salary_history`, `competences`, `hr_notification_dedup` đang trỏ vào `hr_profiles.user_id`.
Chúng phải trỏ vào `hr_profiles.id`, nếu không hồ sơ chưa có tài khoản sẽ không gắn được
bằng cấp hay lịch sử lương — đúng thứ migration này sinh ra để mở.

AN TOÀN DỮ LIỆU
Tại thời điểm chạy: hr_profiles 1 dòng; salary_history / competences / hr_notification_dedup
đều 0 dòng. Dù vậy vẫn backfill đầy đủ theo thứ tự (thêm cột → nạp dữ liệu → đổi khoá),
để migration đúng cả trên bản sao có dữ liệu thật.
"""
from alembic import op

revision: str = "1718870400047"
down_revision: str = "1718870400046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. hr_profiles: khoá riêng + tên + năm sinh ──────────────────────────
    op.execute("ALTER TABLE hr_profiles ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid();")
    op.execute("UPDATE hr_profiles SET id = gen_random_uuid() WHERE id IS NULL;")
    op.execute("ALTER TABLE hr_profiles ALTER COLUMN id SET NOT NULL;")

    # `full_name` về sống trên hồ sơ: hồ sơ chưa có tài khoản thì không có hàng `users`
    # nào để lấy tên ra. Với hồ sơ đã gắn, đây vẫn là tên trên HỒ SƠ NHÂN SỰ —
    # `users.full_name` là tên hiển thị của tài khoản, hai vai trò khác nhau.
    op.execute("ALTER TABLE hr_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);")
    op.execute(
        """
        UPDATE hr_profiles h SET full_name = u.full_name
          FROM users u WHERE u.id = h.user_id AND h.full_name IS NULL;
        """
    )
    op.execute("UPDATE hr_profiles SET full_name = '(chưa có tên)' WHERE full_name IS NULL;")
    op.execute("ALTER TABLE hr_profiles ALTER COLUMN full_name SET NOT NULL;")

    # Năm sinh — cột danh sách CBVC có, mà hệ thống trước nay không có chỗ chứa.
    # SMALLINT + CHECK: đủ cho một năm, và chặn luôn giá trị vô nghĩa.
    op.execute("ALTER TABLE hr_profiles ADD COLUMN IF NOT EXISTS birth_year SMALLINT;")
    op.execute(
        "ALTER TABLE hr_profiles ADD CONSTRAINT ck_hrp_birth_year "
        "CHECK (birth_year IS NULL OR (birth_year >= 1900 AND birth_year <= 2100));"
    )

    # ── 2. Bảng con: thêm profile_id rồi nạp từ user_id ──────────────────────
    for table, col in (
        ("salary_history", "user_id"),
        ("competences", "user_id"),
        ("hr_notification_dedup", "profile_user_id"),
    ):
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS profile_id UUID;")
        op.execute(
            f"UPDATE {table} c SET profile_id = h.id "
            f"FROM hr_profiles h WHERE h.user_id = c.{col};"
        )

    # ── 3. Đổi khoá chính của hr_profiles ────────────────────────────────────
    # Bỏ FK của bảng con TRƯỚC: chúng đang phụ thuộc vào PK(user_id) sắp bị gỡ.
    #
    # TRA TÊN TỪ HỆ THỐNG, KHÔNG VIẾT CỨNG. Tên thật do m4 đặt (fk_sh_profile,
    # fk_comp_profile…) chứ không theo mặc định của Postgres; đoán sai thì lệnh
    # DROP ... IF EXISTS lặng lẽ không làm gì, FK cũ sống sót, và lệnh đổi khoá chính
    # ngay sau đó mới đổ vỡ — một lỗi chỉ lộ ra ở bước sau, rất khó lần.
    op.execute(
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT con.conrelid::regclass AS tbl, con.conname AS name
                  FROM pg_constraint con
                 WHERE con.contype = 'f'
                   AND con.confrelid = 'hr_profiles'::regclass
            LOOP
                EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.name);
            END LOOP;
        END $$;
        """
    )

    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT hr_profiles_pkey;")
    op.execute("ALTER TABLE hr_profiles ADD PRIMARY KEY (id);")

    # user_id thành TUỲ CHỌN + DUY NHẤT. Postgres cho phép nhiều NULL trong UNIQUE,
    # nên nhiều hồ sơ chưa gắn tài khoản cùng tồn tại được, còn đã gắn thì một-một.
    op.execute("ALTER TABLE hr_profiles ALTER COLUMN user_id DROP NOT NULL;")
    op.execute("ALTER TABLE hr_profiles ADD CONSTRAINT uq_hrp_user UNIQUE (user_id);")

    # ── 4. Bảng con trỏ sang khoá mới ────────────────────────────────────────
    op.execute("ALTER TABLE salary_history ALTER COLUMN profile_id SET NOT NULL;")
    op.execute("ALTER TABLE competences ALTER COLUMN profile_id SET NOT NULL;")
    op.execute("ALTER TABLE hr_notification_dedup ALTER COLUMN profile_id SET NOT NULL;")
    op.execute(
        "ALTER TABLE salary_history ADD CONSTRAINT fk_sh_profile "
        "FOREIGN KEY (profile_id) REFERENCES hr_profiles(id) ON DELETE RESTRICT;"
    )
    op.execute(
        "ALTER TABLE competences ADD CONSTRAINT fk_comp_profile "
        "FOREIGN KEY (profile_id) REFERENCES hr_profiles(id) ON DELETE RESTRICT;"
    )
    op.execute(
        "ALTER TABLE hr_notification_dedup ADD CONSTRAINT fk_dedup_profile "
        "FOREIGN KEY (profile_id) REFERENCES hr_profiles(id) ON DELETE CASCADE;"
    )
    op.execute("ALTER TABLE salary_history DROP COLUMN user_id;")
    op.execute("ALTER TABLE competences DROP COLUMN user_id;")
    op.execute("ALTER TABLE hr_notification_dedup DROP COLUMN profile_user_id;")

    # Ràng buộc chống trùng của dedup gắn vào cột cũ nên biến mất cùng cột đó.
    # Dựng lại theo profile_id, GIỮ NGUYÊN TÊN `uq_hrdedup` mà model đang khai —
    # tên lệch giữa DB và model là thứ chỉ lộ ra khi có người đọc lại lược đồ.
    op.execute("ALTER TABLE hr_notification_dedup DROP CONSTRAINT IF EXISTS uq_hrdedup;")
    op.execute(
        "ALTER TABLE hr_notification_dedup ADD CONSTRAINT uq_hrdedup "
        "UNIQUE (profile_id, kind, milestone_days, fire_date);"
    )

    # ── 5. Chỉ mục phục vụ màn hình danh sách + đường gợi ý gắn tài khoản ────
    op.execute("CREATE INDEX IF NOT EXISTS idx_hrp_full_name ON hr_profiles (lower(full_name));")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hrp_unlinked ON hr_profiles (id) WHERE user_id IS NULL;"
    )


def downgrade() -> None:
    # Hồ sơ CHƯA GẮN tài khoản không tồn tại được ở lược đồ cũ (user_id là khoá chính).
    # Từ chối thẳng thay vì xoá âm thầm — mất hồ sơ nhân sự là mất dữ liệu gốc.
    op.execute(
        """
        DO $$
        DECLARE n INT;
        BEGIN
            SELECT count(*) INTO n FROM hr_profiles WHERE user_id IS NULL;
            IF n > 0 THEN
                RAISE EXCEPTION
                    'Còn % hồ sơ nhân sự chưa gắn tài khoản. Lược đồ cũ không chứa được '
                    'chúng — hãy gắn tài khoản hoặc xoá thủ công trước khi hạ cấp.', n;
            END IF;
        END $$;
        """
    )
    for table, col, rule in (
        ("salary_history", "user_id", "RESTRICT"),
        ("competences", "user_id", "RESTRICT"),
        ("hr_notification_dedup", "profile_user_id", "CASCADE"),
    ):
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} UUID;")
        op.execute(
            f"UPDATE {table} c SET {col} = h.user_id "
            f"FROM hr_profiles h WHERE h.id = c.profile_id;"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL;")

        op.execute("ALTER TABLE salary_history DROP CONSTRAINT IF EXISTS fk_sh_profile;")
    op.execute("ALTER TABLE competences DROP CONSTRAINT IF EXISTS fk_comp_profile;")
    op.execute("ALTER TABLE hr_notification_dedup DROP CONSTRAINT IF EXISTS fk_dedup_profile;")
    op.execute("ALTER TABLE salary_history DROP COLUMN profile_id;")
    op.execute("ALTER TABLE competences DROP COLUMN profile_id;")
    op.execute("ALTER TABLE hr_notification_dedup DROP COLUMN profile_id;")

    op.execute("DROP INDEX IF EXISTS idx_hrp_unlinked;")
    op.execute("DROP INDEX IF EXISTS idx_hrp_full_name;")
    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT IF EXISTS uq_hrp_user;")
    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT IF EXISTS ck_hrp_birth_year;")
    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT hr_profiles_pkey;")
    op.execute("ALTER TABLE hr_profiles ALTER COLUMN user_id SET NOT NULL;")
    op.execute("ALTER TABLE hr_profiles ADD PRIMARY KEY (user_id);")
    op.execute("ALTER TABLE hr_profiles DROP COLUMN birth_year;")
    op.execute("ALTER TABLE hr_profiles DROP COLUMN full_name;")
    op.execute("ALTER TABLE hr_profiles DROP COLUMN id;")

    op.execute(
        "ALTER TABLE salary_history ADD CONSTRAINT salary_history_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES hr_profiles(user_id) ON DELETE RESTRICT;"
    )
    op.execute(
        "ALTER TABLE competences ADD CONSTRAINT competences_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES hr_profiles(user_id) ON DELETE RESTRICT;"
    )
    op.execute(
        "ALTER TABLE hr_notification_dedup ADD CONSTRAINT hr_notification_dedup_profile_user_id_fkey "
        "FOREIGN KEY (profile_user_id) REFERENCES hr_profiles(user_id) ON DELETE CASCADE;"
    )
    op.execute(
        "ALTER TABLE hr_notification_dedup ADD CONSTRAINT uq_hnd_key "
        "UNIQUE (profile_user_id, kind, milestone_days, fire_date);"
    )
