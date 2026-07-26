"""Integration (Postgres thật) — báo cáo hoạt động tháng: tạo báo cáo + dòng hoạt động
đổ vào bảng thành tích (report_id), list/get/review/delete."""
import uuid

import pytest

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import Publication, ResearchProject, TeachingCourse
from app.services import activity_report_service as svc

_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _user(role="staff", uid=_ADMIN_ID, dept=None) -> CurrentUser:
    return CurrentUser(
        id=uid, email="u@lims.local", full_name="U", role=role, department_id=dept,
        is_dept_lead=False, is_quality_manager=False, status="active", jti="j", token_exp=9999999999,
    )


def _payload(period="01/2026"):
    return {
        "period_label": period, "academic_year": "2025-2026", "note": "báo cáo tháng 1",
        "teaching": [{"course_name": "Sinh học phân tử", "hk1_theory_hours": 30}],
        "projects": [{"title": "Đề tài A", "level": "institution", "budget_amount": "100000000"}],
        "publications": [
            {"pub_kind": "international", "title": "Paper X", "journal": "Catena", "year": 2025, "is_scie": True},
            {"pub_kind": "conference", "title": "Báo cáo HN", "journal": "Kỷ yếu", "year": 2025},
        ],
        "contracts": [{"title": "HĐ tư vấn", "value_amount": "50000000"}],
        "activities": [{"kind": "cong_doan", "content": "Văn nghệ 8.3"}],
    }


def test_create_report_populates_modules(db):
    admin = _user("admin")
    out = svc.create_report(db, user=admin, payload=_payload(), correlation_id=None, ip=None)
    assert out["status"] == "submitted"
    assert out["counts"] == {"teaching": 1, "projects": 1, "publications": 2, "contracts": 1, "activities": 1}
    rid = uuid.UUID(str(out["id"]))
    # dòng đổ vào bảng thành tích với report_id
    assert db.query(TeachingCourse).filter(TeachingCourse.report_id == rid).count() == 1
    assert db.query(ResearchProject).filter(ResearchProject.report_id == rid).count() == 1
    pubs = db.query(Publication).filter(Publication.report_id == rid).all()
    assert len(pubs) == 2
    assert any(p.type == "conference" for p in pubs) and any(p.is_scie for p in pubs)


def test_duplicate_period_rejected(db):
    admin = _user("admin")
    svc.create_report(db, user=admin, payload=_payload("02/2026"), correlation_id=None, ip=None)
    with pytest.raises(AppException) as e:
        svc.create_report(db, user=admin, payload=_payload("02/2026"), correlation_id=None, ip=None)
    assert e.value.http_status == 409


def test_office_can_list_all_and_review(db):
    reporter = _user("staff", uid=_ADMIN_ID)
    out = svc.create_report(db, user=reporter, payload=_payload("03/2026"), correlation_id=None, ip=None)
    office = _user("office", uid=_ADMIN_ID)  # phải là user thật (FK reviewed_by)
    items, total = svc.list_reports(db, user=office, period="03/2026", department_id=None, status=None, page=1, limit=20)
    assert total >= 1
    reviewed = svc.review_report(db, user=office, report_id=uuid.UUID(str(out["id"])), correlation_id=None, ip=None)
    assert reviewed["status"] == "reviewed"


def test_reporter_role_required(db):
    office = _user("office", uid=uuid.uuid4())
    with pytest.raises(AppException) as e:
        svc.create_report(db, user=office, payload=_payload("04/2026"), correlation_id=None, ip=None)
    assert e.value.http_status == 403


def test_delete_report_removes_entries(db):
    admin = _user("admin")
    out = svc.create_report(db, user=admin, payload=_payload("05/2026"), correlation_id=None, ip=None)
    rid = uuid.UUID(str(out["id"]))
    svc.delete_report(db, user=admin, report_id=rid, correlation_id=None, ip=None)
    assert db.query(ResearchProject).filter(ResearchProject.report_id == rid).count() == 0
    assert db.query(Publication).filter(Publication.report_id == rid).count() == 0
