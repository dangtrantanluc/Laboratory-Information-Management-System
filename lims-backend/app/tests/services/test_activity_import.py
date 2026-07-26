"""Tests cho helper làm sạch của script import hoạt động 2024-2025 (hàm THUẦN)."""
import importlib.util
import pathlib
from decimal import Decimal

# Nạp module script (nằm ngoài package app/) để test helper thuần.
_spec = importlib.util.spec_from_file_location(
    "import_activities",
    pathlib.Path(__file__).resolve().parents[3] / "scripts" / "import_activities_2024_2025.py",
)
imp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(imp)


# ---------- parse_budget ----------
def test_budget_trieu():
    assert imp.parse_budget("100 triệu") == Decimal("100000000")
    assert imp.parse_budget("120 triệu") == Decimal("120000000")


def test_budget_ty():
    assert imp.parse_budget("2 tỷ") == Decimal("2000000000")


def test_budget_numeric_passthrough():
    assert imp.parse_budget(110000000) == Decimal("110000000")


def test_budget_empty():
    assert imp.parse_budget(None) is None
    assert imp.parse_budget("") is None


# ---------- parse_year_range ----------
def test_year_range():
    assert imp.parse_year_range("2023-2025") == (2023, 2025)
    assert imp.parse_year_range("2025") == (2025, 2025)
    assert imp.parse_year_range(None) == (None, None)


# ---------- parse_indexing ----------
def test_indexing_scie_ssci():
    r = imp.parse_indexing("SCIE/SSCI", None, None)
    assert r["is_scie"] and r["is_ssci"] and not r["is_scopus"]


def test_indexing_scopus_in_scie_col():
    # dữ liệu bẩn: "SCOPUS" nằm nhầm ở cột SCIE
    r = imp.parse_indexing("SCOPUS", None, None)
    assert r["is_scopus"] and not r["is_scie"]


def test_indexing_scopus_x_mark():
    r = imp.parse_indexing(None, "x", None)
    assert r["is_scopus"]


def test_indexing_empty():
    r = imp.parse_indexing(None, None, None)
    assert not any(r.values())


# ---------- parse_author_role ----------
def test_author_role_corresponding():
    assert imp.parse_author_role("Tác giả liên hệ") == ("corresponding", True)


def test_author_role_co():
    assert imp.parse_author_role("ĐTG") == ("co", False)


def test_author_role_main():
    assert imp.parse_author_role("TG") == ("main", False)


# ---------- split_members ----------
def test_split_members():
    assert imp.split_members("A, B; C\nD") == ["A", "B", "C", "D"]
    assert imp.split_members("") == []


# ---------- normalize_name / resolve_person ----------
def test_normalize_name_strips_accents():
    assert imp.normalize_name("Trịnh Thị  Phi Ly") == "trinh thi phi ly"


def test_resolve_person_matches_and_falls_back():
    import uuid
    uid = uuid.uuid4()
    index = {"trinh thi phi ly": uid}
    assert imp.resolve_person("Trịnh Thị Phi Ly", index) == (uid, None)
    got_uid, ext = imp.resolve_person("Người Ngoài Hệ Thống", index)
    assert got_uid is None and ext == "Người Ngoài Hệ Thống"
