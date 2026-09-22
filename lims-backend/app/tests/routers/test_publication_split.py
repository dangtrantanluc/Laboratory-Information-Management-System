"""m47 — tách danh mục công bố thành BÀI BÁO và SÁNG CHẾ.

Yêu cầu nghiệp vụ: "tách bài báo và sáng chế riêng ra… như vậy xuất file Excel dễ hơn."

Bộ test này canh hai bất biến, và bất biến thứ hai mới là cái dễ vỡ:

1. **Hai danh mục không giẫm lên nhau** — bài báo không lọt vào danh mục sáng chế và
   ngược lại.
2. **Tách xong vẫn không mất gì.** Bài báo + sáng chế cộng lại phải đúng bằng tổng cũ.
   Báo cáo hội nghị là chỗ dễ rơi nhất: nó không phải bài báo tạp chí, cũng không phải
   văn bằng, nên một cách tách bất cẩn sẽ làm nó biến mất khỏi cả hai màn hình mà không
   ai nhận ra — cho tới kỳ báo cáo cuối năm.
"""
import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_PUBS = "/api/v1/publications"


@pytest.fixture
def seeded(client, as_role):
    """Mỗi loại một bản ghi, đủ để phủ cả ba nhánh phân loại con."""
    as_role("admin")
    made = []
    for body in (
        {"type": "paper", "title": "Bài báo trong nước", "journal": "TC Nông nghiệp",
         "year": 2025, "index_code": "domestic", "pub_scope": "domestic"},
        {"type": "paper", "title": "Bài báo quốc tế", "journal": "Catena",
         "year": 2025, "index_code": "isi_q1", "pub_scope": "international"},
        {"type": "conference", "title": "Báo cáo hội nghị", "journal": "Kỷ yếu HN 2025",
         "year": 2025},
        {"type": "patent", "title": "Sáng chế A", "year": 2025,
         "patent_no": "1-0001", "issuing_authority": "Cục SHTT", "patent_kind": "invention"},
        {"type": "patent", "title": "Giải pháp hữu ích B", "year": 2025,
         "patent_no": "2-0002", "issuing_authority": "Cục SHTT",
         "patent_kind": "utility_solution"},
        {"type": "patent", "title": "Giống cây trồng C", "year": 2025,
         "patent_no": "3-0003", "issuing_authority": "Cục Trồng trọt",
         "patent_kind": "plant_variety"},
    ):
        # API bắt buộc ít nhất một tác giả — công bố không có tác giả thì không
        # truy về được ai, nên đây là ràng buộc đúng chứ không phải rào cản của test.
        r = client.post(
            _PUBS,
            json={
                **body,
                "authors": [
                    {"external_name": "Nguyễn Văn A", "author_order": 1,
                     "is_corresponding": True},
                ],
            },
        )
        assert r.status_code == 201, r.text
        made.append(r.json()["data"])
    return made


def _titles(client, **params) -> set[str]:
    r = client.get(_PUBS, params={"limit": 100, **params})
    assert r.status_code == 200, r.text
    return {p["title"] for p in r.json()["data"]}


class TestLocNhieuLoai:
    """Màn hình "Bài báo" gom bài báo tạp chí + báo cáo hội nghị nên phải lọc hai loại."""

    def test_mot_loai_van_chay_nhu_cu(self, client, seeded):
        assert _titles(client, type="patent") == {
            "Sáng chế A", "Giải pháp hữu ích B", "Giống cây trồng C",
        }

    def test_nhieu_loai_ngan_cach_bang_dau_phay(self, client, seeded):
        assert _titles(client, type="paper,conference") == {
            "Bài báo trong nước", "Bài báo quốc tế", "Báo cáo hội nghị",
        }

    def test_khoang_trang_thua_khong_lam_hong_bo_loc(self, client, seeded):
        """FE ghép chuỗi, nên đừng để một dấu cách làm rỗng kết quả."""
        assert _titles(client, type=" paper , conference ") == {
            "Bài báo trong nước", "Bài báo quốc tế", "Báo cáo hội nghị",
        }

    def test_hai_danh_muc_khong_giam_len_nhau(self, client, seeded):
        bai_bao = _titles(client, type="paper,conference")
        sang_che = _titles(client, type="patent")

        assert bai_bao & sang_che == set()

    def test_tach_xong_khong_mat_ban_ghi_nao(self, client, seeded):
        """Bất biến quan trọng nhất của cả migration này."""
        tat_ca = _titles(client)
        bai_bao = _titles(client, type="paper,conference")
        sang_che = _titles(client, type="patent")

        assert bai_bao | sang_che == tat_ca, (
            "có bản ghi không thuộc màn hình nào — kiểm tra lại type_filter"
        )

    def test_bao_cao_hoi_nghi_khong_bi_roi_ra_ngoai(self, client, seeded):
        """Loại dễ bị bỏ quên nhất: không phải bài báo tạp chí, không phải văn bằng."""
        assert "Báo cáo hội nghị" in _titles(client, type="paper,conference")


class TestDonDanhMucChiSo:
    """m47 — "Chỉ số" chỉ còn nói về xếp hạng tạp chí.

    Trước đây danh mục này trộn ba khái niệm: xếp hạng (ISI/Scopus), phạm vi
    ('domestic') và loại công bố ('conference'). Vì có mục 'domestic' trong ô Chỉ số,
    cùng một sự thật "trong nước hay quốc tế" được lưu ở hai chỗ mà không gì ép chúng
    khớp — nên hai màn hình mới tách theo `pub_scope` có thể ra kết quả khác nhau.
    """

    def test_o_chon_chi_so_khong_con_pham_vi_va_loai(self, client, as_role):
        as_role("admin")

        r = client.get("/api/v1/catalogs/pub-indexes")

        assert r.status_code == 200, r.text
        codes = {c["code"] for c in r.json()["data"]}
        assert "domestic" not in codes, "'Tạp chí trong nước' là PHẠM VI, không phải chỉ số"
        assert "conference" not in codes, "'Kỷ yếu hội nghị' là LOẠI công bố, không phải chỉ số"

    def test_van_con_du_cac_bac_xep_hang_that(self, client, as_role):
        """Đối trọng: dọn dẹp không được cuốn theo thứ đang dùng đúng."""
        as_role("admin")

        codes = {c["code"] for c in client.get("/api/v1/catalogs/pub-indexes").json()["data"]}

        assert {"isi_q1", "isi_q2", "isi_q3", "isi_q4", "scopus"} <= codes

    def test_khong_ban_ghi_nao_con_giu_pham_vi_trong_o_chi_so(self, client, as_role, db):
        from sqlalchemy import text

        as_role("admin")
        con_sot = db.execute(
            text("SELECT count(*) FROM publications WHERE category IN ('domestic','conference')")
        ).scalar_one()

        assert con_sot == 0

    def test_ban_ghi_cu_van_doc_duoc(self, client, as_role, db):
        """Vô hiệu hoá chứ KHÔNG xoá: khoá ngoại và hồ sơ lịch sử phải còn nguyên."""
        from sqlalchemy import text

        as_role("admin")
        con_hang = db.execute(
            text("SELECT count(*) FROM publication_categories WHERE code IN ('domestic','conference')")
        ).scalar_one()

        assert con_hang == 2, "hai mục phải còn trong bảng, chỉ bị ẩn khỏi ô chọn"

    def test_tao_cong_bo_trong_nuoc_khong_can_chi_so(self, client, as_role):
        """Hệ quả trực tiếp: tạp chí trong nước vốn không có xếp hạng nào để chọn."""
        as_role("admin")

        r = client.post(
            _PUBS,
            json={
                "type": "paper", "title": "Công bố trong nước không xếp hạng",
                "journal": "TC Khoa học Nông nghiệp", "year": 2025,
                "pub_scope": "domestic",
                "authors": [{"external_name": "Trần B", "author_order": 1,
                             "is_corresponding": True}],
            },
        )

        assert r.status_code == 201, r.text
        assert r.json()["data"]["pub_scope"] == "domestic"


class TestMucXuatExcel:
    def test_co_du_hai_muc_moi_va_giu_muc_gop_cu(self, client, as_role):
        as_role("admin")

        r = client.get("/api/v1/research-exports")

        assert r.status_code == 200, r.text
        kinds = {k["kind"] for k in r.json()["data"]}
        assert {"papers", "patents"} <= kinds
        # Báo cáo tổng kết năm vẫn cần một file gộp — giữ lại là quyết định, không phải sót.
        assert "publications" in kinds

    def test_moi_muc_chi_mang_cot_cua_chinh_no(self):
        """Đây chính là lý do cô yêu cầu tách: file cũ 18 cột, bỏ trống gần một nửa."""
        from app.services.research_export_service import KINDS

        papers = [c[0] for c in KINDS["papers"].columns]
        patents = [c[0] for c in KINDS["patents"].columns]

        # Cột riêng của sáng chế KHÔNG được xuất hiện trong file bài báo.
        assert not {"Số bằng", "Ngày cấp bằng", "Chủ bằng", "Cơ quan cấp"} & set(papers)
        # …và ngược lại.
        assert not {"DOI", "Chỉ mục", "Phạm vi"} & set(patents)
        # Cả hai vẫn gọn hơn hẳn bản gộp 18 cột.
        assert len(papers) < 18 and len(patents) < 18

    def test_muc_moi_khong_ke_thua_bo_loc_sai(self):
        """`papers` phải lọc đúng hai loại; `patents` đúng một."""
        from app.services.research_export_service import KINDS

        assert KINDS["papers"].fetch_kwargs["type_filter"] == "paper,conference"
        assert KINDS["patents"].fetch_kwargs["type_filter"] == "patent"

    @pytest.mark.parametrize("kind", ["papers", "patents"])
    def test_tai_duoc_file_that(self, client, as_role, seeded, kind):
        as_role("admin")

        r = client.get(
            f"/api/v1/research-exports/{kind}.xlsx",
            params={"from": "2025-01-01", "to": "2025-12-31"},
        )

        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
