"""Dữ liệu DEMO cho Báo cáo phân tích mẫu theo quý (m54) — CHỈ dùng cho bản xem thử.

Dựng đủ mọi trạng thái để kiểm thử cả hai phía (lab và Văn phòng):
  Quý hiện tại
    LAB-HS    Đang nhập     6 dòng (có mã 26N265 dùng chung với LAB-MTD)
    LAB-MTD   Đã nộp        8 dòng  → Văn phòng thử Trả lại / Chốt
    LAB-SHPT  Bị trả lại    5 dòng, kèm lý do → lab thử sửa rồi Nộp lại
    LAB-CNVS  Đã chốt       4 dòng  → Văn phòng thử Mở khoá
    LAB-SKCT  Đã chốt       3 dòng
    LAB-NAM   Đã nộp        0 dòng ("không phát sinh mẫu")
    Các lab còn lại         Chưa bắt đầu
  Hai quý trước: mọi lab đã chốt, 3–6 dòng — để thử xuất Excel một quý đầy đủ và
  thống kê cả năm (tab "Báo cáo phân tích mẫu" ở trang Báo cáo & Thống kê).

Đi qua chính service của tính năng (nộp / trả lại / chốt thật), nên nhật ký, thông báo
và ràng buộc ngày trong quý đều giống khi người dùng thao tác.

Chạy (cần tài khoản lab — seed_role_accounts.py --all-labs — và tài khoản office):
  docker exec lims-demo-api python scripts/seed_demo_quarterly_samples.py

Idempotent: phòng + quý nào đã có báo cáo thì bỏ qua.
"""
import random
import sys
from datetime import timedelta

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.deps import CurrentUser  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.quarterly_sample_report import QuarterlyReport  # noqa: E402
from app.models.sample_flow import TestParameter  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import quarterly_sample_report_service as svc  # noqa: E402

# Loại mẫu + chỉ tiêu ưu tiên (khớp tên trong "BẢNG GIÁ PHÂN TÍCH - 2024") theo phòng.
# Không có trong danh mục thì rơi về "chỉ tiêu ngoài danh mục".
LAB_PROFILE = {
    "LAB-HS": [("food", ["Độ ẩm", "Protein", "Lipid"]), ("soil", ["Độ ẩm"])],
    "LAB-MTD": [("soil", ["pH (H2O)", "Độ ẩm", "Chất hữu cơ"]), ("water", ["pH", "COD", "BOD5"]),
                ("fertilizer", ["Đạm tổng số (N)", "Độ ẩm"])],
    "LAB-SHPT": [("molecular", ["Định danh", "Giải trình tự"])],
    "LAB-CNVS": [("fertilizer", ["Tổng số vi sinh vật hiếu khí"]), ("food", ["Coliforms"])],
    "LAB-SKCT": [("quarantine", ["Tuyến trùng", "Nấm bệnh"])],
    "LAB-NAM": [("other", [])],
    "LAB-CNTB": [("other", [])],
    "LAB-KTMT": [("water", ["pH", "TSS"])],
    "LAB-NNTH": [("fertilizer", ["Độ ẩm"])],
}
EXTRA = ["Tro", "Tro, Xơ thô", "Đường tổng", None, None, None]

# (mã phòng, trạng thái đích, số dòng) cho quý hiện tại.
CURRENT_PLAN = [
    ("LAB-HS", "draft", 6),
    ("LAB-MTD", "submitted", 8),
    ("LAB-SHPT", "returned", 5),
    ("LAB-CNVS", "locked", 4),
    ("LAB-SKCT", "locked", 3),
    ("LAB-NAM", "submitted", 0),
]
SHARED_CODE = "26N265"  # một mẫu, hai phòng cùng phân tích (LAB-HS + LAB-MTD)


def as_current(u: User) -> CurrentUser:
    return CurrentUser(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role,
        department_id=u.department_id, is_dept_lead=False, is_quality_manager=False,
        status="active", jti="seed", token_exp=0,
    )


def prev_quarter(year: int, quarter: int) -> tuple[int, int]:
    return (year - 1, 4) if quarter == 1 else (year, quarter - 1)


class Seeder:
    def __init__(self, db):
        self.db = db
        self.rng = random.Random(2026)
        self.code_seq = 200
        self.params: dict[str, list[TestParameter]] = {}
        for p in db.execute(select(TestParameter).where(TestParameter.is_active)).scalars():
            self.params.setdefault(p.matrix, []).append(p)

    def next_code(self, year: int) -> str:
        self.code_seq += self.rng.randint(1, 4)
        return f"{year % 100}N{self.code_seq}"

    def criteria(self, matrix: str, wanted: list[str]) -> tuple[list, str | None]:
        pool = self.params.get(matrix, [])
        picked = [p for p in pool if p.name in wanted]
        if not picked and pool:
            picked = self.rng.sample(pool, k=min(2, len(pool)))
        extra = self.rng.choice(EXTRA)
        if not picked and not extra:
            extra = "Chỉ tiêu theo yêu cầu khách hàng"
        return [p.id for p in picked[:3]], extra

    def items(self, dept_code: str, year: int, quarter: int, n: int, shared: bool) -> list[dict]:
        start, end = svc.quarter_bounds(year, quarter)
        end = min(end, svc.today_vn())
        span = (end - start).days
        out = []
        for i in range(n):
            matrix, wanted = self.rng.choice(LAB_PROFILE.get(dept_code, [("other", [])]))
            ids, extra = self.criteria(matrix, wanted)
            out.append({
                "sample_code": SHARED_CODE if shared and i == 0 else self.next_code(year),
                "received_date": start + timedelta(days=self.rng.randint(0, span)),
                "matrix": matrix,
                "matrix_other": "Mẫu nấm tươi" if matrix == "other" else None,
                "quantity": self.rng.choice([1, 1, 1, 2, 2, 3, 5]),
                "test_parameter_ids": ids,
                "extra_criteria": extra,
                "note": self.rng.choice([None, None, None, "Mẫu khách gửi bưu điện", "Làm gấp"]),
            })
        return out


def main() -> int:
    db = SessionLocal()
    try:
        labs = {
            d.code: d for d in db.execute(
                select(Department).where(Department.kind == "lab", Department.status == "active")
            ).scalars()
        }
        lab_users = {}
        for u in db.execute(
            select(User).where(User.role.in_(("staff", "lab_manager")), User.status == "active")
            .order_by(User.role)  # lab_manager trước staff
        ).scalars():
            if u.department_id:
                lab_users.setdefault(u.department_id, u)
        office = db.execute(
            select(User).where(User.role == "office", User.status == "active")
        ).scalars().first()
        if office is None:
            print("LỖI: chưa có tài khoản office — chạy seed_role_accounts.py trước.")
            return 1
        reviewer = as_current(office)
        seeder = Seeder(db)
        today = svc.today_vn()
        cur = (today.year, (today.month - 1) // 3 + 1)
        prev = prev_quarter(*cur)
        prev2 = prev_quarter(*prev)

        plans = [
            (q, code, "locked", seeder.rng.randint(3, 6))
            for q in (prev2, prev) for code in sorted(labs)
        ]
        plans += [(cur, code, status, n) for code, status, n in CURRENT_PLAN]

        done = []
        for (year, quarter), code, status, n in plans:
            dept = labs.get(code)
            user = lab_users.get(dept.id) if dept else None
            if dept is None or user is None:
                print(f"  ! bỏ qua {code}: không có phòng hoặc không có tài khoản lab")
                continue
            exists = db.execute(select(QuarterlyReport.id).where(
                QuarterlyReport.department_id == dept.id, QuarterlyReport.year == year,
                QuarterlyReport.quarter == quarter,
            )).first()
            if exists:
                print(f"  = {code} {svc.period_label(year, quarter)} đã có báo cáo — bỏ qua")
                continue
            lab = as_current(user)
            rep = svc.ensure_report(db, user=lab, year=year, quarter=quarter,
                                    correlation_id=None, ip=None)
            if n:
                items = seeder.items(code, year, quarter, n, shared=(code in ("LAB-HS", "LAB-MTD")
                                                                   and (year, quarter) == cur))
                svc.create_items_batch(db, user=lab, report_id=rep["id"], items=items,
                                       correlation_id=None, ip=None)
            if status != "draft":
                svc.submit(db, user=lab, report_id=rep["id"], confirm_empty=(n == 0),
                           lab_note=None if n else "Quý này phòng không nhận mẫu",
                           correlation_id=None, ip=None)
            if status == "returned":
                svc.return_report(
                    db, user=reviewer, report_id=rep["id"],
                    reason="Mẫu đầu danh sách thiếu chỉ tiêu phân tích; kiểm tra lại số lượng "
                           "các mẫu nhận cuối tháng 9.",
                    correlation_id=None, ip=None,
                )
            if status == "locked":
                svc.lock(db, user=reviewer, report_id=rep["id"], correlation_id=None, ip=None)
            done.append((code, svc.period_label(year, quarter), status, n))

        print("\n═══ Báo cáo mẫu demo ═══")
        for code, period, status, n in done:
            print(f"  {period:<14}{code:<10}{status:<11}{n} dòng")
        print(f"\n  Tạo {len(done)} báo cáo. Tài khoản Văn phòng dùng để duyệt: {office.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
