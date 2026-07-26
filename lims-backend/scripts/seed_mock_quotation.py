"""Seed BÁO GIÁ mock từ dữ liệu thật (Bảng báo giá BEJO VIỆT NAM) — để test tính năng m29.

Dữ liệu lấy từ file gốc "1792026 0722 Báo gía - CÔNG TY TNHH BEJO VIỆT NAM.xls"
(đã trích sang JSON vì openpyxl không đọc .xls). Script:
  1) tạo báo giá qua ĐÚNG service (Decimal ở server, không tin số trong file),
  2) tự nối chỉ tiêu với DANH MỤC (test_parameters) khi tên khớp,
  3) ĐỐI CHIẾU tổng tiền hệ thống tính vs tổng trong file → phát hiện lệch ngay.

Chạy:
  docker exec lims-api python scripts/seed_mock_quotation.py docs/mock_quotation_bejo.json
  (thêm --keep để giữ báo giá cũ, mặc định xoá báo giá mock cùng khách trước khi tạo lại)
"""
import argparse
import json
import re
import sys
import unicodedata
from decimal import Decimal

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.deps import CurrentUser  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.quotation import Quotation  # noqa: E402
from app.models.sample_flow import TestParameter  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import quotation_service as svc  # noqa: E402


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s or ""))
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--keep", action="store_true", help="Không xoá báo giá mock cũ")
    args = ap.parse_args()

    data = json.load(open(args.path, encoding="utf-8"))
    cust, rows, file_totals = data["customer"], data["items"], data["file_totals"]

    db = SessionLocal()

    # Đóng vai Phòng nhận mẫu (đúng RBAC lập báo giá)
    u = db.execute(select(User).where(User.email == "reception@lims.local")).scalars().first()
    if u is None:
        print("! không tìm thấy reception@lims.local"); return 1
    actor = CurrentUser(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role,
        department_id=u.department_id, is_dept_lead=False, is_quality_manager=False,
        status=u.status, jti="seed", token_exp=9999999999,
    )

    if not args.keep:
        old = db.execute(
            select(Quotation).where(Quotation.customer_name == cust["name"])
        ).scalars().all()
        for q in old:
            db.delete(q)
        if old:
            db.commit()
            print(f"  đã xoá {len(old)} báo giá mock cũ của khách này")

    # Nối chỉ tiêu với danh mục theo tên (không phân biệt hoa/thường)
    catalog = {norm(p.name): p for p in db.execute(select(TestParameter)).scalars().all()}
    matched = 0
    items = []
    for i, r in enumerate(rows):
        tp = catalog.get(norm(r["parameter_name"]))
        if tp is not None:
            matched += 1
        items.append({
            "sort_order": i,
            "sample_name": r["sample_name"],
            "test_parameter_id": tp.id if tp else None,
            "parameter_name": r["parameter_name"],
            "quantity": r["quantity"],
            "unit_price": r["unit_price"],  # dùng giá trong file (đã thương lượng)
        })

    out = svc.create_quotation(
        db, user=actor,
        fields={
            "customer_name": cust["name"],
            "customer_address": cust.get("address"),
            "customer_email": cust.get("email"),
            "customer_phone": cust.get("phone"),
            "vat_rate": "8",
            "items": items,
        },
        correlation_id="seed-mock", ip=None,
    )

    print(f"  Đã tạo báo giá: {out['code']} — {out['customer_name']}")
    print(f"  Số dòng: {len(out['items'])} | nối được danh mục: {matched}/{len(rows)}")
    print("  ── ĐỐI CHIẾU tổng tiền (hệ thống tính vs file gốc) ──")
    ok = True
    for label, sys_v, file_v in (
        ("Cộng     ", out["subtotal"], file_totals["subtotal"]),
        ("VAT 8%   ", out["vat_amount"], file_totals["vat"]),
        ("Tổng cộng", out["total"], file_totals["total"]),
    ):
        s_d, f_d = Decimal(str(sys_v)), Decimal(str(file_v))
        same = s_d == f_d
        ok = ok and same
        print(f"   {label}: hệ thống={s_d:>16,.0f} | file={f_d:>16,.0f}  {'KHỚP' if same else 'LỆCH!'}")
    print("  => KẾT LUẬN:", "khớp hoàn toàn với file gốc" if ok else "CÓ LỆCH — cần kiểm tra")
    db.close()
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
