"""Báo cáo TỔNG HỢP KHÁCH HÀNG theo kỳ (m50) — phục vụ Văn phòng.

VÌ SAO CẦN
Văn phòng chịu trách nhiệm báo cáo tổng thể hoạt động của Viện, nhưng hai báo cáo sẵn
có chỉ nói về MẪU và HOÁ CHẤT — và báo cáo mẫu còn chặn Văn phòng (B03: khối văn phòng
không xem dữ liệu thử nghiệm). Về phía khách hàng thì không có gì cả: muốn biết tháng
này có bao nhiêu khách mới, ai gửi nhiều mẫu nhất, đã thu được bao nhiêu, thì phải mở
từng phiếu ra đếm tay.

VÌ SAO VĂN PHÒNG ĐƯỢC XEM CÁI NÀY, TRONG KHI BỊ CHẶN Ở BÁO CÁO MẪU
Hai thứ khác nhau. Báo cáo mẫu là dữ liệu THỬ NGHIỆM — chỉ tiêu, kết quả, phòng lab
nào làm. Báo cáo này là dữ liệu THƯƠNG MẠI — khách nào, bao nhiêu phiếu, giá trị bao
nhiêu, thu được chưa. Hợp đồng và hoá đơn vốn đã là việc của Văn phòng (xem W12 trong
lib/rbac.ts và read_roles của routers/customers.py), nên chặn họ ở đây là chặn đúng
người đang phải làm báo cáo.

NGUỒN SỐ LIỆU
    khách mới      customers.created_at trong kỳ
    khách hoạt động khách có ÍT NHẤT MỘT phiếu nhận mẫu trong kỳ
    số phiếu       sample_intakes.received_at trong kỳ
    giá trị báo giá quotations.total của báo giá gắn phiếu trong kỳ
    đã thu         sample_intakes.paid_amount

"Khách mới" và "khách hoạt động" là HAI con số khác nhau và cố ý không cộng vào nhau:
một khách tạo từ năm ngoái mà tháng này gửi mẫu thì hoạt động chứ không mới.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models.customer import Customer
from app.models.quotation import Quotation
from app.models.sample_flow import SampleIntake
from app.services import report_common as rc

# Ai được xem: cùng danh sách với quyền đọc sổ khách hàng (routers/customers.py).
# Khối lab không có mặt — họ bị che PII khách hàng bởi m26, nên một bảng tổng hợp
# xếp hạng khách theo doanh số sẽ là đường vòng qua chính cơ chế đó.
_ALLOWED_ROLES = ("admin", "leader", "reception", "office")

_TOP_LIMIT = 10


def _assert_can_read(user: CurrentUser) -> None:
    if user.role not in _ALLOWED_ROLES:
        raise rc.forbidden("Bạn không có quyền xem báo cáo khách hàng")


def _money(v) -> str:
    return str(v if v is not None else Decimal("0"))


def report_customers(
    db: Session,
    *,
    user: CurrentUser,
    date_from,
    date_to,
    group_by: str,
) -> tuple[dict, dict]:
    _assert_can_read(user)
    rc.validate_group_by(group_by)
    d_from, d_to = rc.resolve_range(date_from, date_to)
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)

    ckey = rc.cache_key(
        "reports_customers", user, None,
        {"from": d_from, "to": d_to, "group_by": group_by},
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(cached=True, extra={
            "from": d_from.isoformat(), "to": d_to.isoformat(), "group_by": group_by,
        })

    live = [Customer.deleted_at.is_(None)]
    in_period = [SampleIntake.received_at >= dt_from, SampleIntake.received_at < dt_to]

    # ── Khách mới trong kỳ ───────────────────────────────────────────────────
    new_rows = db.execute(
        select(Customer.created_at).where(
            *live, Customer.created_at >= dt_from, Customer.created_at < dt_to
        )
    ).scalars().all()

    # ── Phiếu nhận mẫu trong kỳ, kèm khách ───────────────────────────────────
    intakes = db.execute(
        select(
            SampleIntake.id, SampleIntake.customer_id, SampleIntake.customer_name,
            SampleIntake.received_at, SampleIntake.paid_amount,
        ).where(*in_period)
    ).all()

    # ── Giá trị báo giá của các phiếu trong kỳ ───────────────────────────────
    # Bám theo PHIẾU chứ không theo ngày lập báo giá: một báo giá lập tháng sau cho
    # phiếu tháng này vẫn thuộc về doanh số của tháng này.
    quoted_by_intake: dict[uuid.UUID, Decimal] = {}
    if intakes:
        ids = [r.id for r in intakes]
        for q_intake, total in db.execute(
            select(Quotation.intake_id, func.sum(cast(Quotation.total, Numeric(16, 2))))
            .where(Quotation.intake_id.in_(ids), Quotation.deleted_at.is_(None))
            .group_by(Quotation.intake_id)
        ).all():
            quoted_by_intake[q_intake] = total or Decimal("0")

    # ── Gộp theo kỳ ──────────────────────────────────────────────────────────
    series: dict[str, dict] = {}

    def bucket(key: str) -> dict:
        return series.setdefault(key, {
            "period": key, "new_customers": 0, "active_customers": 0,
            "intakes": 0, "quoted_total": Decimal("0"), "paid_total": Decimal("0"),
        })

    for created_at in new_rows:
        bucket(rc.period_key(created_at, group_by))["new_customers"] += 1

    # Khách hoạt động đếm THEO TỪNG KỲ, không cộng dồn: một khách gửi mẫu cả ba tháng
    # là ba lần hoạt động nhưng chỉ một khách — cộng lại sẽ thổi phồng con số.
    active_per_period: dict[str, set] = {}
    overall_active: set = set()
    totals = {"intakes": 0, "quoted": Decimal("0"), "paid": Decimal("0")}
    by_customer: dict[str, dict] = {}

    for r in intakes:
        key = rc.period_key(r.received_at, group_by)
        b = bucket(key)
        b["intakes"] += 1
        totals["intakes"] += 1

        quoted = quoted_by_intake.get(r.id, Decimal("0"))
        paid = r.paid_amount or Decimal("0")
        b["quoted_total"] += quoted
        b["paid_total"] += paid
        totals["quoted"] += quoted
        totals["paid"] += paid

        # Khách vãng lai không có customer_id — gộp theo TÊN đã chụp trên phiếu để
        # họ không biến mất khỏi bảng xếp hạng.
        ident = str(r.customer_id) if r.customer_id else f"name:{r.customer_name}"
        active_per_period.setdefault(key, set()).add(ident)
        overall_active.add(ident)

        c = by_customer.setdefault(ident, {
            "customer_id": r.customer_id, "name": r.customer_name,
            "intakes": 0, "quoted_total": Decimal("0"), "paid_total": Decimal("0"),
            "is_walk_in": r.customer_id is None,
        })
        c["intakes"] += 1
        c["quoted_total"] += quoted
        c["paid_total"] += paid

    for key, idents in active_per_period.items():
        bucket(key)["active_customers"] = len(idents)

    ordered = [
        {**b,
         "quoted_total": _money(b["quoted_total"]),
         "paid_total": _money(b["paid_total"])}
        for _, b in sorted(series.items())
    ]
    top = sorted(
        by_customer.values(),
        key=lambda c: (-c["intakes"], -c["quoted_total"]),
    )[:_TOP_LIMIT]

    data = {
        "summary": {
            "new_customers": len(new_rows),
            "active_customers": len(overall_active),
            "total_customers": db.execute(
                select(func.count()).select_from(Customer).where(*live)
            ).scalar_one(),
            "intakes": totals["intakes"],
            "quoted_total": _money(totals["quoted"]),
            "paid_total": _money(totals["paid"]),
        },
        "series": ordered,
        "top_customers": [
            {**c,
             "customer_id": str(c["customer_id"]) if c["customer_id"] else None,
             "quoted_total": _money(c["quoted_total"]),
             "paid_total": _money(c["paid_total"])}
            for c in top
        ],
    }
    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(cached=False, extra={
        "from": d_from.isoformat(), "to": d_to.isoformat(), "group_by": group_by,
    })
