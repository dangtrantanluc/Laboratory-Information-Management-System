"""Tạo tài khoản THỬ NGHIỆM cho từng vai trò — mật khẩu mặc định Lims@1234.

Dùng cho đợt nghiệm thu (xem docs/HUONG_DAN_KIEM_THU_LIMS_THEO_VAI_TRO.docx): mỗi
vai trò một tài khoản riêng để biết ai đã làm gì khi đối chiếu nhật ký.

Chạy:
  # xem trước, KHÔNG ghi gì
  docker exec lims-api python scripts/seed_role_accounts.py --dry-run

  # tạo thật (dev)
  docker exec lims-api python scripts/seed_role_accounts.py

  # production: đặt đúng tên miền của Viện
  limsc exec -T lims-api python scripts/seed_role_accounts.py --domain lims.dangtrantanluc.id.vn

Idempotent: email đã tồn tại thì BỎ QUA (không ghi đè). Muốn đưa tài khoản cũ về
mật khẩu mặc định thì thêm --reset-existing.

Đi qua user_service.create_user/reset_password chứ không INSERT thẳng, nên vẫn có
bản ghi nhật ký USER_CREATE / PASSWORD_RESET_ADMIN như khi tạo trên giao diện.
"""
import argparse
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import user_service  # noqa: E402

DEFAULT_PASSWORD = "Lims@1234"
LAB = "__LAB__"  # chỗ giữ sẵn, thay bằng --lab-code lúc chạy

# (vai trò, phần trước @ của email, họ tên, mã phòng ban)
# Phòng ban chọn theo đúng nơi vai trò đó làm việc, để dashboard và phạm vi dữ
# liệu theo phòng hiện ra giống thật. admin để trống phòng ban: quản trị viên
# không thuộc phòng nào, gán vào một phòng sẽ làm lệch số liệu của phòng đó.
ACCOUNTS = [
    ("admin", "quantri", "Quản trị viên (tài khoản thử)", None),
    ("leader", "lanhdao", "Ban lãnh đạo (tài khoản thử)", "BGD"),
    ("reception", "nhanmau", "Phòng nhận mẫu (tài khoản thử)", "NM"),
    ("lab_manager", "truongphonglab", "Trưởng phòng lab (tài khoản thử)", LAB),
    ("staff", "ktv", "Kỹ thuật viên (tài khoản thử)", LAB),
    ("qms", "chatluong", "Quản lý chất lượng (tài khoản thử)", "QLCL"),
    ("office", "vanphong", "Văn phòng (tài khoản thử)", "KT"),
]

ROLE_LABELS = {
    "admin": "Quản trị viên",
    "leader": "Ban lãnh đạo",
    "office": "Văn phòng",
    "staff": "KTV",
    "reception": "Phòng nhận mẫu",
    "qms": "Quản lý chất lượng",
    "lab_manager": "Trưởng phòng lab",
}


def parse_args():
    p = argparse.ArgumentParser(
        description="Tạo tài khoản thử nghiệm cho từng vai trò (mật khẩu mặc định Lims@1234)."
    )
    p.add_argument("--domain", default="lims.local",
                   help="Tên miền email, mặc định lims.local")
    p.add_argument("--password", default=DEFAULT_PASSWORD,
                   help=f"Mật khẩu đặt cho các tài khoản, mặc định {DEFAULT_PASSWORD}")
    p.add_argument("--prefix", default="",
                   help="Tiền tố email, vd --prefix thu → thu.ktv@domain")
    p.add_argument("--lab-code", default="LAB-SHPT",
                   help="Mã phòng lab gán cho Trưởng phòng lab và KTV, mặc định LAB-SHPT")
    p.add_argument("--only", default="",
                   help="Chỉ làm một số vai trò, cách nhau bởi dấu phẩy. Vd --only staff,reception")
    p.add_argument("--reset-existing", action="store_true",
                   help="Email đã tồn tại thì đặt lại mật khẩu về mật khẩu mặc định")
    p.add_argument("--set-dept-lead", action="store_true",
                   help="Đặt tài khoản Trưởng phòng lab làm trưởng nhóm của phòng lab đó. "
                        "CẢNH BÁO: ghi đè trưởng nhóm hiện tại của phòng.")
    p.add_argument("--dry-run", action="store_true", help="Chỉ in dự kiến, không ghi gì")
    return p.parse_args()


def main():
    args = parse_args()
    only = {r.strip() for r in args.only.split(",") if r.strip()}
    prefix = f"{args.prefix.strip().strip('.')}." if args.prefix.strip() else ""

    db = SessionLocal()
    try:
        actor = db.execute(
            select(User).where(User.role == "admin", User.status == "active")
            .order_by(User.created_at)
        ).scalars().first()
        if actor is None:
            print("LỖI: không tìm thấy tài khoản admin đang hoạt động để đứng tên tạo.")
            print("      Tài khoản admin gốc do migration m7 sinh ra — kiểm tra lại DB.")
            return 1
        print(f"→ đứng tên: {actor.email}")

        depts = {
            code: dept_id
            for code, dept_id in db.execute(select(Department.code, Department.id)).all()
        }

        created, skipped, reset, failed = [], [], [], []

        for role, local, full_name, dept_code in ACCOUNTS:
            if only and role not in only:
                continue

            code = args.lab_code if dept_code == LAB else dept_code
            dept_id = None
            if code is not None:
                dept_id = depts.get(code)
                if dept_id is None:
                    print(f"  ! phòng ban {code} không có trong DB — tạo {role} mà không gán phòng")

            email = f"{prefix}{local}@{args.domain}"
            existing = db.execute(select(User).where(User.email == email)).scalars().first()

            if existing is not None:
                if not args.reset_existing:
                    skipped.append((role, email, "đã tồn tại"))
                    continue
                if args.dry_run:
                    reset.append((role, email, code or "—"))
                    continue
                user_service.reset_password(
                    db, actor_id=actor.id, user_id=existing.id,
                    new_password=args.password, correlation_id=None, ip=None,
                )
                reset.append((role, email, code or "—"))
                continue

            if args.dry_run:
                created.append((role, email, code or "—"))
                continue

            try:
                user_service.create_user(
                    db, actor_id=actor.id, email=email, full_name=full_name, role=role,
                    department_id=dept_id, password=args.password,
                    is_dept_lead=(args.set_dept_lead and role == "lab_manager" and dept_id is not None),
                    correlation_id=None, ip=None,
                )
                created.append((role, email, code or "—"))
            except Exception as exc:  # noqa: BLE001 — in lỗi từng dòng, không dừng cả mẻ
                db.rollback()
                failed.append((role, email, str(exc)[:120]))

        # ── báo cáo ───────────────────────────────────────────────────────
        head = "═══ DRY-RUN — chưa ghi gì ═══" if args.dry_run else "═══ KẾT QUẢ ═══"
        print(f"\n{head}")

        def show(title, rows, with_pwd=True):
            if not rows:
                return
            print(f"\n{title}")
            print(f"  {'Vai trò':<22}{'Email':<42}{'Phòng':<12}{'Mật khẩu' if with_pwd else ''}")
            for role, email, extra in rows:
                pwd = args.password if with_pwd else extra
                print(f"  {ROLE_LABELS.get(role, role):<22}{email:<42}{extra:<12}{pwd if with_pwd else ''}")

        show("Tạo mới:", created)
        show("Đặt lại mật khẩu:", reset)
        if skipped:
            print("\nBỏ qua (đã tồn tại, dùng --reset-existing nếu muốn đặt lại mật khẩu):")
            for role, email, why in skipped:
                print(f"  {ROLE_LABELS.get(role, role):<22}{email:<42}{why}")
        if failed:
            print("\nLỖI:")
            for role, email, why in failed:
                print(f"  {ROLE_LABELS.get(role, role):<22}{email:<42}{why}")

        print(f"\n  tạo mới: {len(created)} · đặt lại mật khẩu: {len(reset)} · "
              f"bỏ qua: {len(skipped)} · lỗi: {len(failed)}")
        if not args.dry_run and (created or reset):
            print(f"\n  Mật khẩu chung: {args.password}")
            print("  Đây là tài khoản dùng cho đợt kiểm thử. Xong đợt thì khoá lại hoặc")
            print("  đổi mật khẩu — đừng để tài khoản dùng mật khẩu chung tồn tại lâu dài.")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
