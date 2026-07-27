"""Nạp kho biểu mẫu VILAS từ thư mục docs/VILAS _FORM (m28).

    docker compose ... exec -T lims-api python scripts/import_vilas_forms.py /data/vilas [--dry-run]

Cấu trúc nguồn: mỗi thư mục con là một điều khoản ISO/IEC 17025, khớp đúng cây
điều khoản hiển thị trên giao diện:

    VILAS _FORM/2. Mục tiêu chất lượng/...
    VILAS _FORM/5. Yêu cầu về cơ cấu/...
    VILAS _FORM/7. Yêu cầu về quá trình/...

TÊN FILE KHÔNG THEO MỘT QUY TẮC DUY NHẤT — đây là dữ liệu thật, tích tụ nhiều
năm, nên script dò theo thứ tự ưu tiên thay vì ép một khuôn:

    2026_5.2  Xac dinh trach nhiem truong PTN.docx  → năm 2026, điều khoản 5.2
    BM HC.TĐTTNB.01.RIBE. Bien ban hop.docx         → mã "BM HC.TĐTTNB.01.RIBE"
    Quyen han - Trach nhiem.docx                    → không mã, không điều khoản con
                                                      → lấy điều khoản từ thư mục

IDEMPOTENT: bỏ qua biểu mẫu đã có cùng mã, nên chạy lại nhiều lần an toàn. Chạy
--dry-run trước để xem sẽ tạo gì mà không ghi gì vào database.
"""
import argparse
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.deps import CurrentUser  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.form import FormTemplate  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import form_file_service, form_service  # noqa: E402

# Thư mục con → điều khoản gốc. Khớp cây điều khoản trên giao diện.
FOLDER_CLAUSE = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8",
}

# .pptx KHÔNG nằm trong allowlist MIME (attachment_common.GENERIC_ALLOWED_MIME).
# Đó là chủ đích: allowlist chặn mọi thứ ngoài danh sách, không phải chỉ chặn
# thứ nguy hiểm đã biết. Script BÁO CÁO các file bị bỏ thay vì im lặng.
EXT_MIME = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}

# Mã biểu mẫu dạng "BM HC.TĐTTNB.01.RIBE" — bắt tới trước phần mô tả.
RE_CODE = re.compile(r"^(BM\s+[A-Za-zÀ-ỹĐđ0-9.]+(?:\.[A-Za-zÀ-ỹĐđ0-9]+)*)", re.U)
# Tiền tố năm: "2026_..." hoặc "2025_..."
RE_YEAR = re.compile(r"^(20\d{2})[_\s.-]+")
# Điều khoản con: "5.2", "7.5.1" đứng đầu (sau khi đã bỏ tiền tố năm)
RE_CLAUSE = re.compile(r"^(\d\.\d(?:\.\d)?)\s")


def norm(s: str) -> str:
    """Bỏ dấu + hạ chữ thường, để so trùng không phụ thuộc cách gõ tiếng Việt."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    ).lower()


def parse(path: pathlib.Path, folder_clause: str) -> dict:
    """Tách mã / tiêu đề / điều khoản / năm từ tên file."""
    stem = path.stem.strip()
    year = None
    clause = folder_clause

    m = RE_YEAR.match(stem)
    if m:
        year = int(m.group(1))
        stem = stem[m.end():].strip()

    m = RE_CLAUSE.match(stem)
    if m:
        clause = m.group(1)
        stem = stem[m.end():].strip()

    m = RE_CODE.match(stem)
    if m:
        code = m.group(1).strip().rstrip(".")
        title = stem[m.end():].strip().lstrip(".").strip()
    else:
        code = None
        title = stem

    # Bỏ số thứ tự trang trí đầu tiêu đề: "1. Muc tieu chat luong"
    title = re.sub(r"^\d+[.)]\s*", "", title).strip()
    return {"code": code, "title": title or stem, "iso_clause": clause, "year": year}


def unique_code(db, base: str, taken: set) -> str:
    """Mã phải duy nhất (form_service ném DUPLICATE_CODE). Thêm hậu tố khi đụng."""
    code = base
    i = 2
    while code in taken or db.execute(
        select(FormTemplate.id).where(FormTemplate.code == code)
    ).scalar_one_or_none() is not None:
        code = f"{base}-{i}"
        i += 1
    taken.add(code)
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="thư mục VILAS _FORM")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in, không ghi database")
    ap.add_argument("--admin-email", default=None, help="tài khoản đứng tên tạo")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    if not root.is_dir():
        print(f"✗ Không thấy thư mục: {root}")
        return 1

    db = SessionLocal()

    admin = db.execute(
        select(User).where(
            User.email == args.admin_email.lower() if args.admin_email else User.role == "admin"
        ).limit(1)
    ).scalar_one_or_none()
    if admin is None:
        print("✗ Không tìm thấy tài khoản admin để đứng tên tạo biểu mẫu")
        return 1
    user = CurrentUser(
        id=admin.id, email=admin.email, full_name=admin.full_name, role=admin.role,
        department_id=admin.department_id, is_dept_lead=False,
        is_quality_manager=True, status="active", jti="import", token_exp=9_999_999_999,
    )
    print(f"→ đứng tên: {admin.email}")

    created = failed = 0
    unsupported: list[str] = []
    skipped_files: list[str] = []
    taken: set = set()
    seq: dict = {}

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        m = re.match(r"^(\d)\.", folder.name)
        folder_clause = FOLDER_CLAUSE.get(m.group(1)) if m else None
        if folder_clause is None:
            print(f"  ⚠ bỏ qua thư mục không nhận dạng được điều khoản: {folder.name}")
            continue

        print(f"\n── Điều khoản {folder_clause}: {folder.name}")
        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in EXT_MIME:
                unsupported.append(str(f.relative_to(root)))
                continue

            info = parse(f, folder_clause)
            if not info["code"]:
                # Không có mã trong tên file → sinh mã theo điều khoản.
                n = seq.get(info["iso_clause"], 0) + 1
                seq[info["iso_clause"]] = n
                info["code"] = f"BM {info['iso_clause']}.{n:02d}"

            existing = db.execute(
                select(FormTemplate.id).where(FormTemplate.code == info["code"])
            ).scalar_one_or_none()
            # PHÂN BIỆT HAI TÌNH HUỐNG TRÙNG MÃ — chúng cần cách xử lý ngược nhau:
            #
            #   1. Mã đã có trong DB từ lần chạy TRƯỚC → bỏ qua, giữ tính idempotent.
            #   2. Mã vừa dùng trong CHÍNH mẻ này (có trong `taken`) → đây là file
            #      KHÁC vô tình sinh cùng mã, phải cấp mã mới chứ không được bỏ.
            #
            # Dữ liệu thật có nhiều bộ như vậy: BM 7.8.01 ứng với ba tài liệu khác
            # nhau (Phieu ket qua thu nghiem / Test Report / _Form Phieu ket qua).
            # Gộp hai tình huống làm một sẽ âm thầm đánh rơi 13 biểu mẫu.
            if existing is not None and info["code"] not in taken:
                skipped_files.append(f"{info['code']}  ←  {f.relative_to(root)}")
                continue

            # Cấp mã TRƯỚC khi in, để dry-run cho ra đúng mã mà lần chạy thật sẽ
            # dùng. Nếu không, dry-run báo "BM 7.8.01" ba lần rồi lần chạy thật lại
            # ra 7.8.01 / 7.8.01-2 / 7.8.01-3 — người đọc mất tin vào bản xem trước.
            info["code"] = unique_code(db, info["code"], taken)

            if args.dry_run:
                print(f"    + {info['code']:28s} [{info['iso_clause']:>5s}] {info['title'][:52]}")
                created += 1
                continue
            try:
                tpl = form_service.create_template(
                    db, user=user, code=info["code"], title=info["title"],
                    iso_clause=info["iso_clause"], category="BM", year=info["year"],
                    note=None, correlation_id="import-vilas", ip=None,
                )
                form_file_service.replace_file(
                    db, user=user, owner_type=form_file_service.OWNER_TEMPLATE,
                    owner_id=tpl["id"], file_name=f.name, content=f.read_bytes(),
                    mime=EXT_MIME[ext], reason="Nạp từ kho VILAS",
                    expected_attachment_id=None, correlation_id="import-vilas", ip=None,
                )
                created += 1
                print(f"    ✓ {info['code']:28s} {info['title'][:50]}")
            except Exception as exc:  # noqa: BLE001 — một file lỗi không chặn cả mẻ
                failed += 1
                print(f"    ✗ {f.name[:46]}: {type(exc).__name__}: {exc}")
                db.rollback()

    print(f"\n═══ {'DRY-RUN — chưa ghi gì' if args.dry_run else 'Kết quả'} ═══")
    print(f"  tạo mới     : {created}")
    print(f"  đã có, bỏ   : {len(skipped_files)}")
    print(f"  lỗi         : {failed}")
    if skipped_files:
        print("  ── bỏ qua vì trùng mã (file KHÔNG được nạp) ──")
        for sk in skipped_files:
            print(f"      {sk}")
    if unsupported:
        # Báo rõ thay vì im lặng: người dùng cần biết file nào KHÔNG vào hệ thống.
        print(f"  không hỗ trợ: {len(unsupported)} (định dạng ngoài allowlist)")
        for u in unsupported:
            print(f"      {u}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
