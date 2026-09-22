"""Router PHIẾU KẾT QUẢ THỬ NGHIỆM (m46) — BM 7.8/01/RIBE.

Hai nhóm đường dẫn:
  · /intakes/{intake_id}/test-reports  — danh sách và lập mới cho một phiếu nhận mẫu
  · /test-reports/{report_id}/…        — vòng đời của một chứng từ cụ thể

Quyền do `test_report_service` kiểm (`test_report:read` / `test_report:manage`) chứ
không phải `require_permission` ở tầng router: cùng luật đó được `attachment_authz` gọi
lại cho đường generic `POST /attachments`, và đặt luật ở một chỗ là cách duy nhất để hai
đường không lệch nhau.

Mọi endpoint khai `response_model` — test kiến trúc chặn endpoint mới thiếu hợp đồng.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.concurrency import upload_slot
from app.core.deps import CurrentUser, get_current_user
from app.core.request_meta import client_ip
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.test_report import (
    CreateTestReportRequest,
    DeleteTestReportResponse,
    DeliverTestReportRequest,
    IssueTestReportRequest,
    ReviseTestReportRequest,
    RevokeTestReportRequest,
    TestReportDownloadResponse,
    TestReportFileResponse,
    TestReportListResponse,
    TestReportResponse,
    UpdateTestReportRequest,
)
from app.services import test_report_service as svc

router = APIRouter(tags=["m46-test-reports"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


# ═══════════════════════════ Theo phiếu nhận mẫu ═══════════════════════════


@router.get("/intakes/{intake_id}/test-reports", response_model=TestReportListResponse)
def list_test_reports(
    intake_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.list_reports(db, user=user, intake_id=intake_id))


@router.post(
    "/intakes/{intake_id}/test-reports",
    response_model=TestReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_test_report(
    intake_id: uuid.UUID,
    body: CreateTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lập bản NHÁP. Tải tệp lên ở bước sau, rồi mới phát hành."""
    return ok(
        svc.create_report(
            db, user=user, intake_id=intake_id, fields=body.model_dump(),
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


# ═══════════════════════════ Một chứng từ ═══════════════════════════


@router.get("/test-reports/{report_id}", response_model=TestReportResponse)
def get_test_report(
    report_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.get_report(db, user=user, report_id=report_id))


@router.patch("/test-reports/{report_id}", response_model=TestReportResponse)
def update_test_report(
    report_id: uuid.UUID,
    body: UpdateTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        svc.update_report(
            db, user=user, report_id=report_id,
            changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.delete("/test-reports/{report_id}", response_model=DeleteTestReportResponse)
def delete_test_report(
    report_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xoá MỀM, chỉ bản nháp. Đã phát hành thì dùng /revoke."""
    return ok(
        svc.delete_report(
            db, user=user, report_id=report_id,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.post("/test-reports/{report_id}/issue", response_model=TestReportResponse)
def issue_test_report(
    report_id: uuid.UUID,
    body: IssueTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Phát hành — từ đây tệp bị khoá, muốn đổi nội dung phải tạo bản sửa đổi."""
    return ok(
        svc.issue_report(
            db, user=user, report_id=report_id, issued_at=body.issued_at,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.post("/test-reports/{report_id}/deliver", response_model=TestReportResponse)
def deliver_test_report(
    report_id: uuid.UUID,
    body: DeliverTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ghi nhận đã trao khách: ngày, hình thức, người nhận."""
    return ok(
        svc.deliver_report(
            db, user=user, report_id=report_id, fields=body.model_dump(),
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.post("/test-reports/{report_id}/revoke", response_model=TestReportResponse)
def revoke_test_report(
    report_id: uuid.UUID,
    body: RevokeTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thu hồi bản đã phát hành. Báo cho mọi người đã từng tải tệp đó về."""
    return ok(
        svc.revoke_report(
            db, user=user, report_id=report_id, reason=body.reason,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.post(
    "/test-reports/{report_id}/revisions",
    response_model=TestReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def revise_test_report(
    report_id: uuid.UUID,
    body: ReviseTestReportRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bản sửa đổi = bản NHÁP mới version+1; bản cũ tự chuyển 'revoked'."""
    return ok(
        svc.create_revision(
            db, user=user, report_id=report_id, reason=body.reason,
            report_no=body.report_no,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


# ═══════════════════════════ Tệp ═══════════════════════════


@router.post(
    "/test-reports/{report_id}/files",
    response_model=TestReportFileResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_test_report_file(
    report_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    with upload_slot():
        content = file.file.read()
        return ok(
            svc.upload_file(
                db, user=user, report_id=report_id,
                file_name=file.filename or "file", content=content,
                mime=file.content_type,
                correlation_id=_cid(request), ip=client_ip(request),
            )
        )


@router.get(
    "/test-reports/{report_id}/files/{attachment_id}",
    response_model=TestReportDownloadResponse,
)
def download_test_report_file(
    report_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cấp presigned URL và GHI VẾT ai đã lấy chứng từ ra khỏi hệ thống (BR-13)."""
    return ok(
        svc.download_file(
            db, user=user, report_id=report_id, attachment_id=attachment_id,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )


@router.delete(
    "/test-reports/{report_id}/files/{attachment_id}",
    response_model=DeleteTestReportResponse,
)
def delete_test_report_file(
    report_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        svc.delete_file(
            db, user=user, report_id=report_id, attachment_id=attachment_id,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    )
