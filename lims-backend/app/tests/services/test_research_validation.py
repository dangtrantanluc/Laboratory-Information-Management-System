"""Unit tests cho validation bài báo/sáng chế (D2) — ma trận validate dày, dễ hồi quy:
_validate_authors (XOR user_id/external_name, author_order), _validate_pub_fields
(type/year/DOI/paper-patent required).

Trỏ thẳng vào `research.publication_service` chứ không qua mặt tiền
`research_service`: mặt tiền dùng `import *` nên không export tên bắt đầu bằng
`_`, và test ở đây kiểm chính các helper private đó (M-03/T1.1).
"""
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppException
from app.services.research import publication_service as rs


# ===================== _validate_authors =====================

def test_authors_empty_rejected():
    with pytest.raises(AppException) as e:
        rs._validate_authors(MagicMock(), [])
    assert e.value.http_status == 400


def test_author_xor_both_set_rejected():
    a = [{"user_id": uuid.uuid4(), "external_name": "Ngoài", "author_order": 1}]
    with pytest.raises(AppException) as e:
        rs._validate_authors(MagicMock(), a)
    assert e.value.code == "INVALID_AUTHOR"


def test_author_xor_neither_set_rejected():
    a = [{"user_id": None, "external_name": None, "author_order": 1}]
    with pytest.raises(AppException) as e:
        rs._validate_authors(MagicMock(), a)
    assert e.value.code == "INVALID_AUTHOR"


def test_author_order_duplicate_rejected():
    a = [
        {"external_name": "A", "author_order": 1},
        {"external_name": "B", "author_order": 1},
    ]
    with pytest.raises(AppException) as e:
        rs._validate_authors(MagicMock(), a)
    assert e.value.code == "DUPLICATE_AUTHOR_ORDER"


def test_author_order_below_one_rejected():
    a = [{"external_name": "A", "author_order": 0}]
    with pytest.raises(AppException):
        rs._validate_authors(MagicMock(), a)


def test_authors_valid_external_only_ok():
    a = [{"external_name": "Ngoài hệ thống", "author_order": 1}]
    assert rs._validate_authors(MagicMock(), a) == set()  # không có internal user


def test_authors_internal_user_validated_and_returned():
    uid = uuid.uuid4()
    a = [{"user_id": uid, "author_order": 1}]
    with patch.object(rs.hc, "assert_user_exists") as m:
        result = rs._validate_authors(MagicMock(), a)
    m.assert_called_once()
    assert result == {uid}


# ===================== _validate_pub_fields =====================

def _paper(**over):
    # m47 — `pub_scope` là trường BẮT BUỘC của công bố trên tạp chí (nó quyết định
    # công bố nằm ở danh mục trong nước hay quốc tế). `category` (xếp hạng) thành
    # tuỳ chọn, vì tạp chí trong nước thường không có bậc ISI/Scopus nào.
    base = {"type": "paper", "title": "T", "year": 2024, "category": "Q1",
            "journal": "J", "pub_scope": "international"}
    base.update(over)
    return base


def test_pub_invalid_type_rejected():
    with pytest.raises(AppException):
        rs._validate_pub_fields(MagicMock(), {"type": "book", "title": "T", "year": 2024})


def test_pub_year_out_of_range_rejected():
    with pytest.raises(AppException):
        rs._validate_pub_fields(MagicMock(), _paper(year=1800))
    with pytest.raises(AppException):
        rs._validate_pub_fields(MagicMock(), _paper(year=date.today().year + 5))


def test_pub_bad_doi_rejected():
    with pytest.raises(AppException):
        rs._validate_pub_fields(MagicMock(), _paper(doi="not-a-doi"))


def test_pub_paper_thieu_chi_so_van_hop_le():
    """m47 — ĐẢO NGƯỢC luật cũ, có chủ đích.

    Trước m47 công bố trên tạp chí BẮT BUỘC có `category` (chỉ số). Nhưng danh mục chỉ
    số lại chứa sẵn mục 'domestic', nên cách duy nhất để lưu một bài trên tạp chí trong
    nước — vốn không có bậc ISI/Scopus nào — là chọn 'domestic' vào ô XẾP HẠNG. Đó
    chính là đường khiến phạm vi lọt vào ô chỉ số, và cùng một sự thật bị lưu hai chỗ.
    """
    db = MagicMock()
    db.get.return_value = object()

    rs._validate_pub_fields(db, _paper(category=None))  # không raise


def test_pub_paper_thieu_pham_vi_bi_tu_choi():
    """Thứ THỰC SỰ bắt buộc: hai danh mục công bố tách theo trường này."""
    with pytest.raises(AppException) as e:
        rs._validate_pub_fields(MagicMock(), _paper(pub_scope=None))
    assert e.value.code == "VALIDATION_ERROR"


def test_pub_paper_category_not_in_catalog_rejected():
    db = MagicMock()
    db.get.return_value = None  # PublicationCategory không tồn tại
    with pytest.raises(AppException) as e:
        rs._validate_pub_fields(db, _paper())
    assert e.value.code == "INVALID_INDEX"


def test_pub_paper_valid_ok():
    db = MagicMock()
    db.get.return_value = object()  # category tồn tại
    rs._validate_pub_fields(db, _paper(doi="10.1000/xyz"))  # không raise


def test_pub_patent_missing_fields_rejected():
    with pytest.raises(AppException):
        rs._validate_pub_fields(MagicMock(), {"type": "patent", "title": "T", "year": 2024})
