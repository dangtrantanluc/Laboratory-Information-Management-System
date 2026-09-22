"""Nhập DANH SÁCH VIÊN CHỨC - NGƯỜI LAO ĐỘNG (file .docx của Viện) vào Hồ sơ nhân sự.

    python scripts/import_hr_roster.py scripts/nhan_su_2026.json [--commit] [--xoa-vang-mat]

CHẠY LẠI ĐƯỢC (idempotent): khớp theo họ tên đã chuẩn hoá, có rồi thì CẬP NHẬT chứ
không tạo trùng. Chạy hai lần cho ra cùng một kết quả.

KHÔNG GHI ĐÈ BẰNG KHOẢNG TRỐNG. Mỗi bản danh sách của Viện có cột khác nhau: bản 15.9
có năm sinh và diện hợp đồng, bản 2026 thì không mà lại có phòng công tác. Script chỉ
đụng vào những trường CÓ MẶT trong file — nếu không, mỗi lần nhập một bản danh sách mới
sẽ xoá sạch dữ liệu mà bản trước đã mang vào.

KHÔNG TẠO TÀI KHOẢN. Từ m48 hồ sơ nhân sự đứng độc lập; người nào đã có tài khoản
trùng tên thì script GỢI Ý ở phần tổng kết để người quản trị tự bấm gắn — không tự
gắn, vì trùng họ tên là chuyện bình thường và gắn nhầm sẽ nối hồ sơ lương của người
này vào tài khoản người khác.

Không có --commit thì chỉ CHẠY THỬ: in ra những gì sẽ làm rồi rollback.
"""
import json
import sys
import unicodedata as ud
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.hr import Competence, HrProfile  # noqa: E402
from app.models.user import User  # noqa: E402

# Ngạch trong file là chữ viết tắt của ngành; hồ sơ cần chức danh đọc được.
NGACH = {
    "GVC": "Giảng viên chính", "GV": "Giảng viên", "CV": "Chuyên viên",
    "NCV": "Nghiên cứu viên", "KTV": "Kỹ thuật viên", "KS": "Kỹ sư",
    "TG": "Trợ giảng",
}
# Bản 2026 viết tắt cả học vị; bản 15.9 ghi đầy đủ nên map này chỉ mở rộng, không ép.
HOC_VI = {"TS": "Tiến sĩ", "ThS": "Thạc sĩ", "KS": "Kỹ sư", "NCS": "Nghiên cứu sinh"}
# NCS là TÌNH TRẠNG ĐÀO TẠO (đang làm nghiên cứu sinh), không phải tấm bằng đã có.
# Ghi nó vào năng lực kiểu "degree" sẽ khai khống bằng cấp, nên chỉ báo ở tổng kết.
KHONG_PHAI_BANG = {"Nghiên cứu sinh"}
# Hai diện trong file → danh mục contract_types có sẵn.
DIEN = {"civil_servant": "civil_servant", "contract": "indefinite"}


def norm(v: str) -> str:
    return " ".join(ud.normalize("NFC", v or "").split()).lower()


def fold(v: str) -> str:
    """Bỏ toàn bộ dấu để khớp tên qua khác biệt CHÍNH TẢ DẤU THANH.

    "Thuỳ" và "Thùy" là cùng một cái tên nhưng khác nhau từng byte: dấu huyền đặt
    trên `u` hay trên `y` là hai cách gõ đều hợp lệ và các bản danh sách của Viện
    dùng lẫn lộn. So khớp NFC sẽ trượt và script tạo ra hồ sơ thứ hai cho cùng một
    người. Đây là đường DỰ PHÒNG: chỉ dùng khi khớp chính xác thất bại, và chỉ nhận
    khi kết quả là DUY NHẤT — bỏ dấu thì "Hà" và "Hạ" cũng chập làm một.
    """
    return "".join(c for c in ud.normalize("NFD", norm(v)) if not ud.combining(c))


def main() -> int:
    path = Path(sys.argv[1])
    commit = "--commit" in sys.argv
    xoa_vang_mat = "--xoa-vang-mat" in sys.argv
    people = json.loads(path.read_text(encoding="utf-8"))
    db = SessionLocal()
    tao = capnhat = nang_luc = 0
    goi_y: list[tuple[str, str]] = []
    ghi_chu: list[str] = []
    da_khop: set[str] = set()

    try:
        phong = {d.code: d for d in db.execute(select(Department)).scalars()}
        users = {norm(u.full_name): u for u in db.execute(select(User)).scalars()}
        hoso = list(db.execute(select(HrProfile)).scalars())
        existing = {norm(p.full_name): p for p in hoso}
        # Nhiều hồ sơ có thể chập vào một khoá bỏ dấu; giữ danh sách để phát hiện.
        folded: dict[str, list[HrProfile]] = {}
        for p in hoso:
            folded.setdefault(fold(p.full_name), []).append(p)

        for r in people:
            ten = r["ho_ten"]
            key = norm(ten)
            p = existing.get(key)
            if p is None:
                dup = folded.get(fold(ten), [])
                if len(dup) == 1:
                    p = dup[0]
                    ghi_chu.append(f"'{ten}' khớp '{p.full_name}' nhờ bỏ dấu — giữ tên cũ")
                elif len(dup) > 1:
                    ten_dup = ", ".join(f"'{d.full_name}'" for d in dup)
                    ghi_chu.append(f"⚠ '{ten}' bỏ dấu trùng nhiều hồ sơ ({ten_dup}) — BỎ QUA")
                    continue

            hv = HOC_VI.get(r.get("hoc_vi") or "", r.get("hoc_vi"))
            ngach = r.get("ngach")
            # Ngạch là chức danh. Không có ngạch thì giữ chức danh cũ, chỉ hồ sơ mới
            # mới cần giá trị thay thế.
            job = NGACH.get(ngach or "", ngach) if ngach else None

            if p is None:
                p = HrProfile(full_name=ten, job_title=job or r.get("chuyen_nganh") or "Nhân viên")
                db.add(p)
                db.flush()
                existing[key] = p
                folded.setdefault(fold(ten), []).append(p)
                tao += 1
            else:
                if job:
                    p.job_title = job
                capnhat += 1
            da_khop.add(p.id)

            if r.get("nam_sinh") is not None:
                p.birth_year = r["nam_sinh"]
            if r.get("dien"):
                p.contract_type = DIEN[r["dien"]]
            if r.get("chuc_vu"):
                p.position = r["chuc_vu"]
            if r.get("phong"):
                d = phong.get(r["phong"])
                if d is None:
                    ghi_chu.append(f"⚠ '{ten}': không có phòng mã {r['phong']} — bỏ trống")
                else:
                    p.department_id = d.id

            # Học vị + chuyên ngành thuộc về NĂNG LỰC (bằng cấp), không phải ô chức danh.
            if hv and hv not in KHONG_PHAI_BANG:
                da_co = db.execute(
                    select(Competence).where(
                        Competence.profile_id == p.id, Competence.kind == "degree"
                    )
                ).scalars().all()
                # So theo HỌC VỊ chứ không theo cả dòng: bản 15.9 ghi chuyên ngành của
                # TẤM BẰNG, bản 2026 ghi chuyên môn CÔNG TÁC. Cùng một người, cùng bằng
                # tiến sĩ, hai bản ghi hai ngành khác nhau — so cả dòng sẽ đẻ ra tấm
                # bằng thứ hai không có thật.
                if not any(c.title == hv or c.title.startswith(f"{hv} —") for c in da_co):
                    nganh = r.get("chuyen_nganh")
                    db.add(Competence(
                        profile_id=p.id, kind="degree",
                        title=f"{hv} — {nganh}" if nganh else hv,
                    ))
                    nang_luc += 1
            elif hv in KHONG_PHAI_BANG:
                ghi_chu.append(f"'{ten}': danh sách ghi {r['hoc_vi']} (đang đào tạo) — "
                               f"không ghi thành bằng cấp")

            u = users.get(key)
            if u is not None and p.user_id is None:
                goi_y.append((ten, str(u.email)))

        # ── Người có trong sổ mà không còn trong danh sách ────────────────────
        # Chỉ xét hồ sơ CHƯA GẮN TÀI KHOẢN: hồ sơ đã gắn là một lối đăng nhập đang
        # sống (kể cả tài khoản vận hành/thử), không phải một dòng của bảng danh sách.
        vang_mat = [p for p in hoso if p.id not in da_khop and p.user_id is None]
        for p in vang_mat:
            if not xoa_vang_mat:
                ghi_chu.append(f"'{p.full_name}' có trong sổ nhưng KHÔNG có trong danh sách mới")
                continue
            con = db.execute(
                select(Competence).where(Competence.profile_id == p.id)
            ).scalars().all()
            for c in con:
                db.delete(c)
            db.delete(p)
            ghi_chu.append(f"XOÁ '{p.full_name}' (kèm {len(con)} năng lực) — không còn trong danh sách")
        db.flush()

        print(f"  hồ sơ tạo mới       : {tao}")
        print(f"  hồ sơ cập nhật      : {capnhat}")
        print(f"  bằng cấp ghi nhận   : {nang_luc}")
        print(f"  gợi ý gắn tài khoản : {len(goi_y)}")
        for ten, mail in goi_y:
            print(f"      · {ten} ↔ {mail}")
        if ghi_chu:
            print(f"  ghi chú             : {len(ghi_chu)}")
            for g in ghi_chu:
                print(f"      · {g}")

        if commit:
            db.commit()
            print("\n✔ ĐÃ GHI vào cơ sở dữ liệu")
        else:
            db.rollback()
            print("\n… CHẠY THỬ — chưa ghi gì. Thêm --commit để ghi thật.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
