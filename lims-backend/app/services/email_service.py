"""Email service — gửi mail giao dịch qua SMTP (m30).

Dùng `smtplib` của thư viện chuẩn, KHÔNG thêm dependency mới.

Chế độ hoạt động phụ thuộc `SMTP_HOST`:
  - Có cấu hình  → gửi thật.
  - Bỏ trống     → chế độ DEV: ghi nội dung (kèm link) ra log ở mức WARNING để lập
                   trình viên copy link mà test, không cần SMTP server.

Nguyên tắc:
  - Gửi mail KHÔNG BAO GIỜ được làm hỏng request nghiệp vụ. Mọi lỗi SMTP đều nuốt
    và ghi log — người dùng đã đăng ký xong thì không thể rollback chỉ vì SMTP sập.
  - Không log token/link ở môi trường production.
"""
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from app.config import settings

logger = logging.getLogger("lims.email")


def _send(to: str, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
    """Gửi 1 mail. Trả True nếu đã gửi thật, False nếu chỉ ghi log (chế độ dev).

    Không raise — caller không cần try/except.
    """
    if not settings.smtp_enabled:
        # Chế độ dev: ghi ra log để test luồng mà không cần SMTP.
        # Ở production, thiếu SMTP là lỗi cấu hình → log ERROR để đội vận hành thấy.
        if settings.is_production:
            logger.error(
                "SMTP chưa cấu hình — KHÔNG gửi được mail",
                extra={"to": to, "subject": subject},
            )
        else:
            logger.warning(
                "[DEV] SMTP chưa cấu hình — nội dung mail ghi ra log:\n"
                "──────── TO: %s ────────\nSUBJECT: %s\n%s\n────────────────────────",
                to,
                subject,
                text_body,
            )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_sender))
    msg["To"] = to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if settings.smtp_ssl:
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
            )
        else:
            server = smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
            )
        with server:
            server.ehlo()
            if settings.smtp_starttls and not settings.smtp_ssl:
                server.starttls()
                server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Đã gửi mail", extra={"to": to, "subject": subject})
        return True
    except Exception as exc:  # noqa: BLE001 — SMTP lỗi KHÔNG được làm hỏng nghiệp vụ
        logger.error(
            "Gửi mail thất bại",
            extra={"to": to, "subject": subject, "error": str(exc)},
        )
        return False


# ──────────────────────────── Khung HTML dùng chung ────────────────────────────

_BRAND = "Viện Nghiên cứu Công nghệ Sinh học và Môi trường"
_SUB_BRAND = "Trường Đại học Nông Lâm TP. Hồ Chí Minh"


def _wrap_html(title: str, body_html: str, cta_label: str = "", cta_url: str = "") -> str:
    cta = (
        f'<p style="margin:28px 0"><a href="{cta_url}" '
        'style="background:#1a6e4a;color:#fff;text-decoration:none;padding:12px 24px;'
        'border-radius:8px;display:inline-block;font-weight:600">'
        f"{cta_label}</a></p>"
        if cta_url
        else ""
    )
    fallback = (
        f'<p style="color:#52564c;font-size:13px">Nút không bấm được? Dán liên kết này '
        f'vào trình duyệt:<br><span style="word-break:break-all;color:#1a6e4a">{cta_url}</span></p>'
        if cta_url
        else ""
    )
    return f"""<!doctype html>
<html lang="vi"><body style="margin:0;background:#f6f7f1;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif">
  <div style="max-width:560px;margin:32px auto;background:#fff;border:1px solid #e2e4d8;border-radius:12px;overflow:hidden">
    <div style="background:linear-gradient(90deg,#1a6e4a,#5a8a6c);padding:20px 24px;color:#fff">
      <div style="font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:.5px">{_BRAND}</div>
      <div style="font-size:12px;opacity:.85">{_SUB_BRAND}</div>
    </div>
    <div style="padding:24px;color:#1a1f1b;line-height:1.6">
      <h1 style="margin:0 0 12px;font-size:18px">{title}</h1>
      {body_html}
      {cta}
      {fallback}
    </div>
    <div style="padding:14px 24px;background:#f9faf4;color:#52564c;font-size:12px;border-top:1px solid #e2e4d8">
      Đây là thư tự động từ Hệ thống Quản lý Phòng Thí nghiệm (VILAS). Vui lòng không trả lời thư này.
    </div>
  </div>
</body></html>"""


# ──────────────────────────── Các loại mail ────────────────────────────


def send_email_verification(*, to: str, full_name: str, verify_url: str) -> bool:
    """Mail xác thực địa chỉ email sau khi đăng ký."""
    hours = settings.email_verify_ttl_hours
    text = (
        f"Chào {full_name},\n\n"
        "Bạn vừa đăng ký tài khoản trên Hệ thống Quản lý Phòng Thí nghiệm của "
        f"{_BRAND}.\n\n"
        f"Vui lòng mở liên kết sau để xác thực địa chỉ email (hiệu lực {hours} giờ):\n"
        f"{verify_url}\n\n"
        "Sau khi xác thực, tài khoản sẽ chờ Quản trị viên duyệt và gán vai trò. "
        "Bạn sẽ nhận được thư thông báo khi tài khoản được kích hoạt.\n\n"
        "Nếu bạn không thực hiện đăng ký này, hãy bỏ qua thư.\n"
    )
    html = _wrap_html(
        "Xác thực địa chỉ email",
        f"<p>Chào <strong>{full_name}</strong>,</p>"
        "<p>Bạn vừa đăng ký tài khoản trên Hệ thống Quản lý Phòng Thí nghiệm. "
        f"Liên kết xác thực có hiệu lực <strong>{hours} giờ</strong>.</p>"
        "<p style='color:#52564c'>Sau khi xác thực, tài khoản sẽ chờ Quản trị viên duyệt "
        "và gán vai trò. Bạn sẽ nhận được thư khi tài khoản được kích hoạt.</p>",
        "Xác thực email",
        verify_url,
    )
    return _send(to, "Xác thực email — Hệ thống LIMS Viện CNSH & Môi trường", text, html)


def send_password_reset(*, to: str, full_name: str, reset_url: str) -> bool:
    """Mail chứa liên kết đặt lại mật khẩu."""
    minutes = settings.password_reset_ttl_minutes
    text = (
        f"Chào {full_name},\n\n"
        "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.\n\n"
        f"Mở liên kết sau để đặt mật khẩu mới (hiệu lực {minutes} phút, dùng một lần):\n"
        f"{reset_url}\n\n"
        "Nếu bạn KHÔNG yêu cầu việc này, hãy bỏ qua thư — mật khẩu hiện tại vẫn an toàn "
        "và không có gì thay đổi.\n"
    )
    html = _wrap_html(
        "Đặt lại mật khẩu",
        f"<p>Chào <strong>{full_name}</strong>,</p>"
        "<p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. "
        f"Liên kết có hiệu lực <strong>{minutes} phút</strong> và chỉ dùng được một lần.</p>"
        "<p style='color:#ac6014'>Nếu bạn không yêu cầu, hãy bỏ qua thư này — mật khẩu "
        "hiện tại vẫn an toàn.</p>",
        "Đặt mật khẩu mới",
        reset_url,
    )
    return _send(to, "Đặt lại mật khẩu — Hệ thống LIMS", text, html)


def send_account_approved(*, to: str, full_name: str, role_label: str, login_url: str) -> bool:
    """Mail báo tài khoản đã được Quản trị viên duyệt."""
    text = (
        f"Chào {full_name},\n\n"
        f"Tài khoản của bạn đã được Quản trị viên duyệt với vai trò: {role_label}.\n\n"
        f"Đăng nhập tại: {login_url}\n\n"
        "Lần đăng nhập đầu tiên, hệ thống sẽ yêu cầu bạn đổi mật khẩu.\n"
    )
    html = _wrap_html(
        "Tài khoản đã được kích hoạt",
        f"<p>Chào <strong>{full_name}</strong>,</p>"
        f"<p>Tài khoản của bạn đã được Quản trị viên duyệt với vai trò "
        f"<strong>{role_label}</strong>.</p>",
        "Đăng nhập ngay",
        login_url,
    )
    return _send(to, "Tài khoản LIMS đã được kích hoạt", text, html)


def send_account_rejected(*, to: str, full_name: str, reason: str) -> bool:
    """Mail báo yêu cầu mở tài khoản bị từ chối."""
    text = (
        f"Chào {full_name},\n\n"
        "Rất tiếc, yêu cầu mở tài khoản của bạn chưa được chấp thuận.\n\n"
        f"Lý do: {reason}\n\n"
        "Vui lòng liên hệ Văn phòng Viện nếu cần hỗ trợ thêm.\n"
    )
    html = _wrap_html(
        "Yêu cầu mở tài khoản chưa được chấp thuận",
        f"<p>Chào <strong>{full_name}</strong>,</p>"
        "<p>Rất tiếc, yêu cầu mở tài khoản của bạn chưa được chấp thuận.</p>"
        f"<p><strong>Lý do:</strong> {reason}</p>"
        "<p style='color:#52564c'>Vui lòng liên hệ Văn phòng Viện nếu cần hỗ trợ.</p>",
    )
    return _send(to, "Yêu cầu mở tài khoản LIMS", text, html)


def send_password_changed_notice(*, to: str, full_name: str, ip: Optional[str]) -> bool:
    """Cảnh báo mật khẩu vừa bị đổi — giúp phát hiện chiếm tài khoản."""
    where = f" từ địa chỉ IP {ip}" if ip else ""
    text = (
        f"Chào {full_name},\n\n"
        f"Mật khẩu tài khoản của bạn vừa được thay đổi{where}.\n\n"
        "Nếu KHÔNG phải bạn thực hiện, hãy liên hệ ngay Quản trị viên — tài khoản "
        "của bạn có thể đã bị truy cập trái phép.\n"
    )
    html = _wrap_html(
        "Mật khẩu vừa được thay đổi",
        f"<p>Chào <strong>{full_name}</strong>,</p>"
        f"<p>Mật khẩu tài khoản của bạn vừa được thay đổi{where}.</p>"
        "<p style='color:#bb332c'><strong>Nếu không phải bạn thực hiện</strong>, hãy liên hệ "
        "ngay Quản trị viên — tài khoản có thể đã bị truy cập trái phép.</p>",
    )
    return _send(to, "Cảnh báo: mật khẩu LIMS vừa được thay đổi", text, html)
