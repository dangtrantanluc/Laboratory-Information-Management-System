"""Tests cho attachment_common — MIME allowlist + inline-safety.

Regression cho stored-XSS fix (PRODUCTION_READINESS_REVIEW §Security: unrestricted
upload + same-origin inline serving): HTML/SVG KHÔNG được qua allowlist và KHÔNG bao
giờ được coi là an toàn để serve inline.
"""
import pytest

from app.core.exceptions import AppException
from app.services import attachment_common as ac


def test_pdf_and_images_allowed():
    for mime in ("application/pdf", "image/png", "image/jpeg"):
        ac.check_mime(mime)  # không raise


def test_html_rejected_on_upload():
    with pytest.raises(AppException) as exc:
        ac.check_mime("text/html", allowed=ac.GENERIC_ALLOWED_MIME)
    assert exc.value.code == "INVALID_FILE_TYPE"


def test_svg_rejected_on_upload():
    with pytest.raises(AppException):
        ac.check_mime("image/svg+xml", allowed=ac.GENERIC_ALLOWED_MIME)


def test_none_mime_rejected():
    with pytest.raises(AppException):
        ac.check_mime(None)


def test_docx_allowed_in_generic_but_not_base():
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ac.check_mime(docx, allowed=ac.GENERIC_ALLOWED_MIME)  # generic OK (documents)
    with pytest.raises(AppException):
        ac.check_mime(docx, allowed=ac.BASE_ALLOWED_MIME)  # base (samples) không nhận docx


def test_inline_safe_only_for_allowlisted():
    assert ac.is_inline_safe("application/pdf") is True
    assert ac.is_inline_safe("image/png") is True


def test_inline_unsafe_for_html_svg():
    assert ac.is_inline_safe("text/html", allowed=ac.GENERIC_ALLOWED_MIME) is False
    assert ac.is_inline_safe("image/svg+xml", allowed=ac.GENERIC_ALLOWED_MIME) is False
    assert ac.is_inline_safe(None) is False
