-- ============================================================================
-- LIMS — Seed BỔ SUNG (chạy SAU seed_demo.sql)
-- Lấp 3 bảng còn trống mà UI có trang/tab hiển thị:
--   17: sample_handovers        → tab "Chuỗi hành trình mẫu" (chain of custody)
--   18: document_access_log     → trang "Thống kê truy cập tài liệu" (M3.3)
--   19: chemical_recheck_records→ lịch sử "Kiểm tra lại hóa chất" (M2.3)
-- An toàn re-run: fixed-UUID + ON CONFLICT DO NOTHING; access_log guard IF-empty.
-- ============================================================================
BEGIN;

-- ── 17. sample_handovers — chuỗi bàn giao mẫu (single & multi-hop) ──────────
INSERT INTO sample_handovers (id, sample_id, from_user, to_user, reason, at) VALUES
 -- SP-2026-0001 (custodian a3): 1 chặng
 ('00000000-0000-0000-0000-000000170001','00000000-0000-0000-0000-000000030001','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a3','Phân công ban đầu cho KTV thực hiện', now() - interval '6 days'),
 -- SP-2026-0002 (custodian a4): 2 chặng
 ('00000000-0000-0000-0000-000000170002','00000000-0000-0000-0000-000000030002','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a3','Giao KTV chạy phân tích', now() - interval '9 days'),
 ('00000000-0000-0000-0000-000000170003','00000000-0000-0000-0000-000000030002','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a4','Chuyển cho người hoàn thiện & nhập kết quả', now() - interval '7 days'),
 -- SP-2026-0004 (custodian a8, overdue)
 ('00000000-0000-0000-0000-000000170004','00000000-0000-0000-0000-000000030004','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a8','Điều phối mẫu quá tải sang KTV khác', now() - interval '5 days'),
 -- SP-2026-0005 (d3 vi sinh, custodian a6)
 ('00000000-0000-0000-0000-000000170005','00000000-0000-0000-0000-000000030005','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000a6','Giao KTV phòng Vi sinh', now() - interval '4 days'),
 -- SP-2026-0006 (d3, custodian a5 — trả về trưởng nhóm duyệt)
 ('00000000-0000-0000-0000-000000170006','00000000-0000-0000-0000-000000030006','00000000-0000-0000-0000-0000000000a6','00000000-0000-0000-0000-0000000000a5','Trả mẫu về trưởng nhóm để duyệt kết quả', now() - interval '2 days'),
 -- SP-2026-0009 (custodian a3): 2 chặng — bàn giao ca
 ('00000000-0000-0000-0000-000000170007','00000000-0000-0000-0000-000000030009','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a4','Giao KTV', now() - interval '12 days'),
 ('00000000-0000-0000-0000-000000170008','00000000-0000-0000-0000-000000030009','00000000-0000-0000-0000-0000000000a4','00000000-0000-0000-0000-0000000000a3','Bàn giao ca trực', now() - interval '10 days')
ON CONFLICT (id) DO NOTHING;

-- ── 19. chemical_recheck_records — lịch sử kiểm tra lại hóa chất ────────────
INSERT INTO chemical_recheck_records (id, lot_id, checked_at, result, note, next_recheck_date, checked_by, created_at) VALUES
 ('00000000-0000-0000-0000-000000190001','00000000-0000-0000-0000-000000070001','2026-01-15','pass','Định lượng đạt chuẩn, ngoại quan bình thường','2026-07-15','00000000-0000-0000-0000-0000000000a3', now() - interval '170 days'),
 ('00000000-0000-0000-0000-000000190002','00000000-0000-0000-0000-000000070001','2026-07-01','pass','Kiểm tra định kỳ 6 tháng — đạt','2027-01-01','00000000-0000-0000-0000-0000000000a3', now() - interval '3 days'),
 ('00000000-0000-0000-0000-000000190003','00000000-0000-0000-0000-000000070002','2026-03-10','pass','Nồng độ HCl 37% đạt, chưa có dấu hiệu bay hơi','2026-09-10','00000000-0000-0000-0000-0000000000a3', now() - interval '116 days'),
 ('00000000-0000-0000-0000-000000190004','00000000-0000-0000-0000-000000070004','2026-02-01','pass','Methanol HPLC — độ tinh khiết đạt','2026-08-01','00000000-0000-0000-0000-0000000000a3', now() - interval '153 days'),
 ('00000000-0000-0000-0000-000000190005','00000000-0000-0000-0000-000000070003','2026-04-20','fail','Nồng độ giảm dưới tiêu chuẩn — đề nghị thanh lý lô', NULL,'00000000-0000-0000-0000-0000000000a3', now() - interval '75 days'),
 ('00000000-0000-0000-0000-000000190006','00000000-0000-0000-0000-000000070005','2026-05-05','pass','Thạch dinh dưỡng — vô trùng, không nhiễm','2026-11-05','00000000-0000-0000-0000-0000000000a5', now() - interval '60 days'),
 ('00000000-0000-0000-0000-000000190007','00000000-0000-0000-0000-000000070006','2026-06-01','pass','Kali dicromat — tinh thể khô, đạt','2026-12-01','00000000-0000-0000-0000-0000000000a3', now() - interval '33 days')
ON CONFLICT (id) DO NOTHING;

-- ── 18. document_access_log — lượt xem/tải/sửa (guard: chỉ seed khi trống) ──
DO $$
BEGIN
IF (SELECT count(*) FROM document_access_log) = 0 THEN
  -- VIEW — tài liệu phòng Hóa (d1/d2), phân bổ theo trọng số
  INSERT INTO document_access_log (document_id, version_id, user_id, action, at)
  SELECT d.doc, d.ver,
    (ARRAY['00000000-0000-0000-0000-0000000000a1'::uuid,
           '00000000-0000-0000-0000-0000000000a2'::uuid,
           '00000000-0000-0000-0000-0000000000a3'::uuid,
           '00000000-0000-0000-0000-0000000000a4'::uuid,
           '00000000-0000-0000-0000-0000000000a8'::uuid])[1 + (g % 5)],
    'view', now() - (g * interval '9 hours')
  FROM (VALUES
    ('00000000-0000-0000-0000-000000090001'::uuid,'00000000-0000-0000-0000-0000000a0002'::uuid, 12),
    ('00000000-0000-0000-0000-000000090002'::uuid,'00000000-0000-0000-0000-0000000a0003'::uuid, 7),
    ('00000000-0000-0000-0000-000000090003'::uuid,'00000000-0000-0000-0000-0000000a0004'::uuid, 5),
    ('00000000-0000-0000-0000-000000090004'::uuid,'00000000-0000-0000-0000-0000000a0005'::uuid, 4)
  ) AS d(doc, ver, n), generate_series(1, d.n) AS g;

  -- VIEW — tài liệu phòng Vi sinh (d3)
  INSERT INTO document_access_log (document_id, version_id, user_id, action, at)
  SELECT d.doc, d.ver,
    (ARRAY['00000000-0000-0000-0000-0000000000a1'::uuid,
           '00000000-0000-0000-0000-0000000000a5'::uuid,
           '00000000-0000-0000-0000-0000000000a6'::uuid])[1 + (g % 3)],
    'view', now() - (g * interval '13 hours')
  FROM (VALUES
    ('00000000-0000-0000-0000-000000090005'::uuid,'00000000-0000-0000-0000-0000000a0006'::uuid, 4),
    ('00000000-0000-0000-0000-000000090006'::uuid,'00000000-0000-0000-0000-0000000a0007'::uuid, 3)
  ) AS d(doc, ver, n), generate_series(1, d.n) AS g;

  -- DOWNLOAD
  INSERT INTO document_access_log (document_id, version_id, user_id, action, at)
  SELECT doc, ver, usr, 'download', now() - (dago * interval '1 day')
  FROM (VALUES
    ('00000000-0000-0000-0000-000000090001'::uuid,'00000000-0000-0000-0000-0000000a0002'::uuid,'00000000-0000-0000-0000-0000000000a3'::uuid, 2),
    ('00000000-0000-0000-0000-000000090001'::uuid,'00000000-0000-0000-0000-0000000a0002'::uuid,'00000000-0000-0000-0000-0000000000a2'::uuid, 5),
    ('00000000-0000-0000-0000-000000090002'::uuid,'00000000-0000-0000-0000-0000000a0003'::uuid,'00000000-0000-0000-0000-0000000000a4'::uuid, 3),
    ('00000000-0000-0000-0000-000000090003'::uuid,'00000000-0000-0000-0000-0000000a0004'::uuid,'00000000-0000-0000-0000-0000000000a1'::uuid, 1),
    ('00000000-0000-0000-0000-000000090004'::uuid,'00000000-0000-0000-0000-0000000a0005'::uuid,'00000000-0000-0000-0000-0000000000a3'::uuid, 6),
    ('00000000-0000-0000-0000-000000090005'::uuid,'00000000-0000-0000-0000-0000000a0006'::uuid,'00000000-0000-0000-0000-0000000000a5'::uuid, 2)
  ) AS d(doc, ver, usr, dago);

  -- EDIT (tạo phiên bản / chỉnh sửa metadata)
  INSERT INTO document_access_log (document_id, version_id, user_id, action, at)
  SELECT doc, ver, usr, 'edit', now() - (dago * interval '1 day')
  FROM (VALUES
    ('00000000-0000-0000-0000-000000090001'::uuid,'00000000-0000-0000-0000-0000000a0002'::uuid,'00000000-0000-0000-0000-0000000000a2'::uuid, 8),
    ('00000000-0000-0000-0000-000000090002'::uuid,'00000000-0000-0000-0000-0000000a0003'::uuid,'00000000-0000-0000-0000-0000000000a2'::uuid, 10),
    ('00000000-0000-0000-0000-000000090005'::uuid,'00000000-0000-0000-0000-0000000a0006'::uuid,'00000000-0000-0000-0000-0000000000a5'::uuid, 4)
  ) AS d(doc, ver, usr, dago);
END IF;
END $$;

COMMIT;

-- Kết quả
SELECT 'sample_handovers' t, count(*) c FROM sample_handovers
UNION ALL SELECT 'chemical_recheck_records', count(*) FROM chemical_recheck_records
UNION ALL SELECT 'document_access_log', count(*) FROM document_access_log
ORDER BY 1;
