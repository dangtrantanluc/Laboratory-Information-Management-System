"""Xuất Excel danh sách Nghiên cứu & Đào tạo — /research-exports.

ROUTER RIÊNG, KHÔNG NHÉT VÀO research.py
research.py đang ở 743/800 dòng (scripts/check-file-size.mjs — trần chỉ được HẠ).
Tám endpoint xuất sẽ đẩy nó vượt trần. Tách ra cũng đúng ranh giới: research.py lo
CRUD nghiệp vụ, file này lo một việc khác hẳn là kết xuất báo cáo.

ĐỌC ĐƯỢC THÌ XUẤT ĐƯỢC, KHÔNG HƠN
Guard giống hệt các endpoint danh sách (`_guard_read`: mọi vai trò đã đăng nhập), vì
phạm vi dữ liệu thật sự do chính hàm list_* quyết định — người dùng chỉ xuất được
đúng những dòng họ thấy trên màn hình. Siết thêm ở đây sẽ tạo ra tình huống khó hiểu:
nhìn thấy dữ liệu trên màn nhưng không tải về được.

export_slot(): openpyxl là CPU-bound. Không có semaphore thì một người bấm liên tục
chiếm hết CPU của cả bốn worker — cùng lý do endpoint xuất báo giá đã dùng nó.
"""
from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.concurrency import export_slot
from app.core.deps import CurrentUser, get_current_user
from app.core.rate_limit import rate_limit
from app.core.request_meta import client_ip
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.research_export import ExportKindListResponse
from app.services import research_export_service as export_svc

router = APIRouter(tags=["m4-research-exports"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


@router.get("/research-exports", response_model=ExportKindListResponse)
def list_export_kinds(user: CurrentUser = Depends(get_current_user)):
    """Các mục xuất được, kèm tên trường thời gian mà mỗi mục lọc theo.

    Giao diện dựng danh sách từ đây thay vì hard-code, và hiển thị đúng nhãn ("Ngày
    ký", "Năm công bố"…) để người dùng biết khoảng thời gian đang lọc theo cái gì.
    """
    return ok(export_svc.kind_options())


@router.get(
    "/research-exports/{kind}.xlsx",
    # Trả file nhị phân, không trả JSON — khai tường minh để test hợp đồng API biết
    # response_model ở đây là vô nghĩa (xem tests/architecture/test_response_contract).
    response_class=Response,
    dependencies=[Depends(rate_limit("research-export", limit=20, window_seconds=60))],
)
def export_research_xlsx(
    request: Request,
    kind: str = Path(description="research-projects | publications | papers | patents | "
                                 "research-contracts | community-services | "
                                 "student-mentorships | teaching-courses | "
                                 "training-certificates | staff-activities"),
    date_from: Optional[date] = Query(
        default=None, alias="from", description="Từ ngày (YYYY-MM-DD). Bỏ trống = không giới hạn."
    ),
    date_to: Optional[date] = Query(
        default=None, alias="to", description="Đến ngày (YYYY-MM-DD). Bỏ trống = không giới hạn."
    ),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tải danh sách một mục Nghiên cứu & Đào tạo ra Excel, lọc theo khoảng thời gian.

    Mỗi mục lọc theo ngày nghiệp vụ của riêng nó (ngày ký hợp đồng, ngày thực hiện…);
    ba mục chỉ lưu NĂM thì khoảng ngày được quy về khoảng năm. Sheet ghi rõ tiêu chí
    đã áp và số bản ghi bị loại vì thiếu dữ liệu thời gian — xem docstring của
    research_export_service.
    """
    with export_slot():
        content, filename = export_svc.export_xlsx(
            db, user=user, kind=kind, date_from=date_from, date_to=date_to,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    return Response(
        content=content,
        media_type=_XLSX_MIME,
        headers={
            # Khai CẢ HAI dạng: `filename=` cho client đọc bằng regex đơn giản (helper
            # apiDownload của frontend chỉ bắt dạng này), `filename*=` theo RFC 5987 cho
            # trình duyệt. Tên file đã là slug không dấu nên hai dạng luôn khớp nhau.
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )
