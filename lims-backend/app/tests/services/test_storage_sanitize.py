"""Tests cho _sanitize_file_name (L6) — allowlist ký tự, chặn traversal/CRLF/null/độ dài."""
from app.services import storage_service as ss


def test_keeps_safe_chars():
    assert ss._sanitize_file_name("Report_2026-01.pdf") == "Report_2026-01.pdf"


def test_strips_path_separators_and_traversal():
    out = ss._sanitize_file_name("../../etc/passwd")
    assert "/" not in out and ".." not in out.strip("_")


def test_strips_crlf_and_quotes_header_injection():
    out = ss._sanitize_file_name('a"; \r\nContent-Type: text/html')
    assert '"' not in out and "\r" not in out and "\n" not in out


def test_strips_null_byte():
    out = ss._sanitize_file_name("evil\x00.pdf")
    assert "\x00" not in out


def test_empty_or_all_bad_falls_back():
    assert ss._sanitize_file_name("") == "file"
    assert ss._sanitize_file_name("///") == "file"


def test_truncates_long_names():
    out = ss._sanitize_file_name("a" * 500)
    assert len(out) <= 120


def test_unicode_replaced():
    out = ss._sanitize_file_name("báo_cáo_hóa_chất.xlsx")
    # ký tự ngoài [A-Za-z0-9._-] → '_'; đuôi & phần ascii giữ lại
    assert out.endswith(".xlsx") and " " not in out
