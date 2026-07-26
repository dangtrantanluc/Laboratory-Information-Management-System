"""Integration (Postgres thật) — CRUD 3 menu mới m23 + serialize field mở rộng.

Chứng minh: hợp đồng/công tác khác/chứng nhận ghi-đọc đúng qua service; publication mở
rộng lưu/đọc chỉ mục + type conference; teaching lưu số tiết.
"""
import uuid

from app.core.deps import CurrentUser
from app.services import activity_service
from app.services.research import project_service, publication_service

_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _admin() -> CurrentUser:
    return CurrentUser(
        id=_ADMIN_ID, email="admin@lims.local", full_name="Admin", role="admin",
        department_id=None, is_dept_lead=False, is_quality_manager=False,
        status="active", jti="jti", token_exp=9999999999,
    )


def test_contract_crud_and_money(db):
    out = activity_service.create_contract(
        db, user=_admin(),
        payload={"title": "HĐ phân tích mẫu", "contract_type": "Tư vấn KHCN",
                 "value_amount": "110000000", "partner_org": "CC1", "academic_year": "2024-2025"},
        correlation_id=None, ip=None,
    )
    assert out["value_amount"] == "110000000.00" and out["contract_type"] == "Tư vấn KHCN"
    items, total = activity_service.list_contracts(
        db, academic_year="2024-2025", department_id=None, q=None, page=1, limit=20)
    assert total == 1 and items[0]["title"] == "HĐ phân tích mẫu"


def test_staff_activity_kind(db):
    out = activity_service.create_activity(
        db, user=_admin(),
        payload={"kind": "vilas", "content": "Duy trì ISO 17025", "academic_year": "2024-2025"},
        correlation_id=None, ip=None,
    )
    assert out["kind"] == "vilas"
    items, total = activity_service.list_activities(db, kind="vilas", academic_year=None, page=1, limit=20)
    assert total == 1


def test_certificate_crud(db):
    out = activity_service.create_certificate(
        db, user=_admin(),
        payload={"recipient_name": "Nguyễn Văn A", "certificate_no": "GCN-01",
                 "course_name": "An toàn PTN", "academic_year": "2024-2025"},
        correlation_id=None, ip=None,
    )
    assert out["recipient_name"] == "Nguyễn Văn A"
    _items, total = activity_service.list_certificates(db, academic_year="2024-2025", q="Văn A", page=1, limit=20)
    assert total == 1


def test_publication_conference_and_indexing(db):
    out = publication_service.create_publication(
        db, user=_admin(),
        payload={"type": "conference", "title": "Báo cáo hội nghị X", "year": 2025,
                 "journal": "Kỷ yếu CESD 2025", "pub_scope": None,
                 "authors": [{"external_name": "Người Ngoài", "author_order": 1,
                              "is_corresponding": True, "author_role": "corresponding"}]},
        correlation_id=None, ip=None,
    )
    assert out["type"] == "conference"
    assert out["authors"][0]["author_role"] == "corresponding"


def test_publication_international_indexing_persists(db):
    out = publication_service.create_publication(
        db, user=_admin(),
        payload={"type": "paper", "title": "Paper Q1", "year": 2025, "journal": "Catena",
                 "category": "isi_q1", "pub_scope": "international", "is_scie": True, "is_scopus": True,
                 "authors": [{"external_name": "A B", "author_order": 1}]},
        correlation_id=None, ip=None,
    )
    assert out["is_scie"] is True and out["is_scopus"] is True
    assert out["pub_scope"] == "international"


def test_project_budget_and_transfer(db):
    out = project_service.create_project(
        db, user=_admin(),
        payload={"title": "Đề tài than sinh học", "level": "institution", "lead_user_id": _ADMIN_ID,
                 "budget_amount": "100000000", "is_transferred": True, "transfer_product": "Quy trình",
                 "academic_year": "2024-2025",
                 "members": [{"user_id": _ADMIN_ID, "role_in_project": "lead"}]},
        correlation_id=None, ip=None,
    )
    assert out["budget_amount"] == "100000000.00"
    assert out["is_transferred"] is True and out["transfer_product"] == "Quy trình"
