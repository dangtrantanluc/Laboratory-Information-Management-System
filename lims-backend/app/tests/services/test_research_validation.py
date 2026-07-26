"""Unit tests cho validation research_service (D2) — ma trận validate dày, dễ hồi quy:
_validate_authors (XOR user_id/external_name, author_order), _validate_pub_fields
(type/year/DOI/paper-patent required)."""
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppException
from app.services import research_service as rs


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
    base = {"type": "paper", "title": "T", "year": 2024, "category": "Q1", "journal": "J"}
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


def test_pub_paper_missing_category_rejected():
    with pytest.raises(AppException) as e:
        rs._validate_pub_fields(MagicMock(), _paper(category=None))
    assert e.value.code == "INVALID_INDEX"


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
