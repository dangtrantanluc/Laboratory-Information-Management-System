-- ============================================================================
-- LIMS — Seed dữ liệu demo (mock) cho luồng NHẬN & CHUYỂN MẪU (BM 7.1/01, 7.1/02)
--
-- Phủ ĐỦ 6 trạng thái phiếu để màn hình có gì mà xem, không phải bấm tay từng cái:
--   received → quoted → quote_accepted → paid → dispatched → completed  (+1 cancelled)
-- và đủ 5 trạng thái lượt chuyển: sent · received · in_progress · done · returned.
--
-- An toàn re-run: ON CONFLICT DO NOTHING theo PK.
-- ID đánh theo khối hex tiếp nối seed_demo.sql:
--   18 test_parameter · 19 sample_intake · 1a sample_dispatch · 1b quotation
-- Phụ thuộc: seed_demo.sql (khách hàng khối 01) phải chạy TRƯỚC.
-- ============================================================================
BEGIN;

-- ── Danh mục chỉ tiêu (m27) — bảng giá để báo giá và chuyển mẫu tham chiếu ──
INSERT INTO test_parameters (id, matrix, sample_matrix, name, method, unit, unit_price,
                             turnaround_days, department_id, is_accredited, is_active, sort_order) VALUES
 ('00000000-0000-0000-0000-000000180001','water','Nước thải, nước mặt','pH','TCVN 6492:2011','-',80000,3,'00000000-0000-0000-0000-000000000e23',true,true,1),
 ('00000000-0000-0000-0000-000000180002','water','Nước thải','COD','SMEWW 5220C:2017','mg/L',250000,5,'00000000-0000-0000-0000-000000000e23',true,true,2),
 ('00000000-0000-0000-0000-000000180003','water','Nước thải','BOD5','SMEWW 5210B:2017','mg/L',280000,5,'00000000-0000-0000-0000-000000000e23',true,true,3),
 ('00000000-0000-0000-0000-000000180004','water','Nước sinh hoạt','Tổng Coliforms','TCVN 6187-2:1996','MPN/100mL',180000,4,'00000000-0000-0000-0000-000000000e13',true,true,4),
 ('00000000-0000-0000-0000-000000180005','food','Thủy sản','Cadimi (Cd)','AOAC 999.11','mg/kg',450000,7,'00000000-0000-0000-0000-000000000e22',true,true,5),
 ('00000000-0000-0000-0000-000000180006','food','Thủy sản','Chì (Pb)','AOAC 999.11','mg/kg',450000,7,'00000000-0000-0000-0000-000000000e22',true,true,6),
 ('00000000-0000-0000-0000-000000180007','food','Dược liệu, thực phẩm','Độ ẩm','TCVN 9934:2013','%',120000,3,'00000000-0000-0000-0000-000000000e22',false,true,7),
 ('00000000-0000-0000-0000-000000180008','molecular','Mẫu sinh học','Định danh loài bằng giải trình tự gen','HD PP.SHPT.01/RIBE','-',1200000,10,'00000000-0000-0000-0000-000000000e11',false,true,8),
 ('00000000-0000-0000-0000-000000180009','soil','Đất trồng trọt','Nitơ tổng số','TCVN 6498:1999','%',210000,5,'00000000-0000-0000-0000-000000000e24',true,true,9),
 ('00000000-0000-0000-0000-00000018000a','food','Thực phẩm','Salmonella spp.','TCVN 10780-1:2017','/25g',320000,6,'00000000-0000-0000-0000-000000000e13',true,true,10)
ON CONFLICT (id) DO NOTHING;

-- ── Phiếu nhận mẫu (BM 7.1/01) ─────────────────────────────────────────────
-- received_by/created_by = reception@lims.local (a9); department_id = Phòng Nhận mẫu (f1).
INSERT INTO sample_intakes
 (id, code, customer_id, customer_name, address, tax_code, contact_person, phone, email,
  description, due_date, result_language, return_method, fee_note, other_request,
  status, payment_status, paid_amount, payment_date, payment_ref,
  department_id, received_by, created_by, received_at) VALUES

 -- 1) Vừa tiếp nhận, chưa báo giá.
 ('00000000-0000-0000-0000-000000190001','NM-2026-0101','00000000-0000-0000-0000-000000010001',
  'Công ty CP Dược Hậu Giang','288 Bis Nguyễn Văn Cừ, Q. Ninh Kiều, TP. Cần Thơ','1800156801',
  'Ms. Lan','0292 389 0000','lan.qa@dhgpharma.com.vn',
  'Viên nang cứng, 3 lô sản xuất, bao bì nguyên vẹn','20/09/2026','vi','email',NULL,
  'Gửi bản mềm phiếu kết quả trước khi gửi bản cứng.',
  'received','unpaid',NULL,NULL,NULL,
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '2 day'),

 -- 2) Đã báo giá, chờ khách trả lời.
 ('00000000-0000-0000-0000-000000190002','NM-2026-0102','00000000-0000-0000-0000-000000010005',
  'Công ty TNHH Thủy sản Minh Phú','KCN Khánh An, H. U Minh, Tỉnh Cà Mau','2000103546',
  'Bộ phận QA','0290 3612 8','qa@minhphu.com',
  'Tôm thẻ đông lạnh, 2 mẫu, bảo quản -18°C','25/09/2026','en','email','1.800.000 đ',NULL,
  'quoted','unpaid',NULL,NULL,NULL,
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '5 day'),

 -- 3) Khách đồng ý giá, chưa chuyển tiền.
 ('00000000-0000-0000-0000-000000190003','NM-2026-0103','00000000-0000-0000-0000-000000010002',
  'Viện Kiểm nghiệm ATVSTP Quốc gia','65 Phạm Thận Duật, Q. Cầu Giấy, TP. Hà Nội','0100112233',
  'Phòng Hợp tác',NULL,'contact@nifc.gov.vn',
  'Mẫu so sánh liên phòng, 1 mẫu nước','30/09/2026','vi','mail','510.000 đ','Kèm biên bản so sánh liên phòng.',
  'quote_accepted','unpaid',NULL,NULL,NULL,
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '7 day'),

 -- 4) Đã thanh toán, chờ chuyển lab.
 ('00000000-0000-0000-0000-000000190004','NM-2026-0104','00000000-0000-0000-0000-000000010003',
  'Nguyễn Văn Khách','12 Lê Lợi, Q.1, TP. Hồ Chí Minh',NULL,
  'Nguyễn Văn Khách','0905 123 456',NULL,
  'Nước giếng khoan sinh hoạt, 1 can 2L','18/09/2026','vi','direct','260.000 đ',NULL,
  'paid','paid',260000, current_date - 3,'CK-20260901-0007',
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '9 day'),

 -- 5) Đã chuyển lab, đang chạy — phiếu "sống" nhất để xem tab Mẫu chuyển đến.
 ('00000000-0000-0000-0000-000000190005','NM-2026-0105','00000000-0000-0000-0000-000000010001',
  'Công ty CP Dược Hậu Giang','288 Bis Nguyễn Văn Cừ, Q. Ninh Kiều, TP. Cần Thơ','1800156801',
  'Trần Quốc Bảo','0913 445 776','bao.rd@dhgpharma.com.vn',
  'Cao dược liệu, 2 mẫu, lọ thủy tinh nút kín','22/09/2026','vi','email','1.320.000 đ',NULL,
  'dispatched','paid',1320000, current_date - 6,'CK-20260828-0031',
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '12 day'),

 -- 6) Đã trả kết quả — có đủ kết quả để xem phiếu chuyển mẫu in ra.
 ('00000000-0000-0000-0000-000000190006','NM-2026-0106','00000000-0000-0000-0000-000000010005',
  'Công ty TNHH Thủy sản Minh Phú','KCN Khánh An, H. U Minh, Tỉnh Cà Mau','2000103546',
  'Bộ phận QA','0290 3612 8','qa@minhphu.com',
  'Tôm sú đông lạnh xuất khẩu, 1 mẫu','05/09/2026','en','email','900.000 đ',NULL,
  'completed','paid',900000, current_date - 20,'CK-20260814-0012',
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '25 day'),

 -- 7) Đã hủy — khách rút yêu cầu (mặt sau BM 7.1/01, mục CAM KẾT CỦA KHÁCH HÀNG).
 ('00000000-0000-0000-0000-000000190007','NM-2026-0107','00000000-0000-0000-0000-000000010004',
  'Khoa Hóa — Nội bộ','Nhà A2, Trường ĐH Nông Lâm TP.HCM',NULL,
  'ThS. Trần Văn Nội',NULL,'noibo@lims.local',
  'Mẫu đất thí nghiệm, 3 mẫu','—','vi','direct',NULL,'Khách rút yêu cầu ngày 30/08/2026.',
  'cancelled','waived',NULL,NULL,NULL,
  '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000a9','00000000-0000-0000-0000-0000000000a9', now() - interval '15 day')
ON CONFLICT (id) DO NOTHING;

-- ── Lượt chuyển mẫu (BM 7.1/02) ────────────────────────────────────────────
-- dispatched_by = reception (a9). Phủ đủ 5 trạng thái của lượt chuyển.
INSERT INTO sample_dispatches
 (id, intake_id, sample_name, quantity, chi_tieu, test_parameter_id, don_vi, phuong_phap,
  ket_qua, can_bo, unit_price, target_department_id, status, note,
  dispatched_by, dispatched_at, received_at, completed_at) VALUES

 -- Phiếu 5 (đang chạy): 3 chỉ tiêu, 3 trạng thái khác nhau.
 ('00000000-0000-0000-0000-0000001a0001','00000000-0000-0000-0000-000000190005','Cao dược liệu lô A',1,
  'Độ ẩm','00000000-0000-0000-0000-000000180007','%','TCVN 9934:2013',
  '8,4','KS. Lê Thị Hương',120000,'00000000-0000-0000-0000-000000000e22','done',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '11 day', now() - interval '10 day', now() - interval '4 day'),

 ('00000000-0000-0000-0000-0000001a0002','00000000-0000-0000-0000-000000190005','Cao dược liệu lô B',1,
  'Định danh loài bằng giải trình tự gen','00000000-0000-0000-0000-000000180008','-','HD PP.SHPT.01/RIBE',
  NULL,'CN. Vũ Đức Sơn',1200000,'00000000-0000-0000-0000-000000000e11','in_progress','Đang chạy PCR, chờ giải trình tự.',
  '00000000-0000-0000-0000-0000000000a9', now() - interval '11 day', now() - interval '9 day', NULL),

 ('00000000-0000-0000-0000-0000001a0003','00000000-0000-0000-0000-000000190005','Cao dược liệu lô B',1,
  'Salmonella spp.','00000000-0000-0000-0000-00000018000a','/25g','TCVN 10780-1:2017',
  NULL,NULL,320000,'00000000-0000-0000-0000-000000000e13','received',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '11 day', now() - interval '8 day', NULL),

 -- Phiếu 4 (đã thanh toán): vừa chuyển, lab chưa nhận → 'sent'.
 ('00000000-0000-0000-0000-0000001a0004','00000000-0000-0000-0000-000000190004','Nước giếng khoan',1,
  'Tổng Coliforms','00000000-0000-0000-0000-000000180004','MPN/100mL','TCVN 6187-2:1996',
  NULL,NULL,180000,'00000000-0000-0000-0000-000000000e13','sent',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '1 day', NULL, NULL),

 ('00000000-0000-0000-0000-0000001a0005','00000000-0000-0000-0000-000000190004','Nước giếng khoan',1,
  'pH','00000000-0000-0000-0000-000000180001','-','TCVN 6492:2011',
  NULL,NULL,80000,'00000000-0000-0000-0000-000000000e23','sent',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '1 day', NULL, NULL),

 -- Phiếu 6 (đã trả KQ): đủ kết quả, in phiếu chuyển mẫu ra là thấy hết các cột.
 ('00000000-0000-0000-0000-0000001a0006','00000000-0000-0000-0000-000000190006','Tôm sú đông lạnh',1,
  'Cadimi (Cd)','00000000-0000-0000-0000-000000180005','mg/kg','AOAC 999.11',
  '0,082','KS. Hoàng Văn Long',450000,'00000000-0000-0000-0000-000000000e22','done',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '24 day', now() - interval '23 day', now() - interval '18 day'),

 ('00000000-0000-0000-0000-0000001a0007','00000000-0000-0000-0000-000000190006','Tôm sú đông lạnh',1,
  'Chì (Pb)','00000000-0000-0000-0000-000000180006','mg/kg','AOAC 999.11',
  '< 0,05 (LOD)','KS. Hoàng Văn Long',450000,'00000000-0000-0000-0000-000000000e22','done',NULL,
  '00000000-0000-0000-0000-0000000000a9', now() - interval '24 day', now() - interval '23 day', now() - interval '18 day'),

 -- Trạng thái 'returned': mẫu không đạt yêu cầu kỹ thuật, lab trả lại.
 ('00000000-0000-0000-0000-0000001a0008','00000000-0000-0000-0000-000000190006','Tôm sú đông lạnh',1,
  'Độ ẩm','00000000-0000-0000-0000-000000180007','%','TCVN 9934:2013',
  NULL,NULL,120000,'00000000-0000-0000-0000-000000000e22','returned','Mẫu rã đông khi tới phòng, không đủ điều kiện thử.',
  '00000000-0000-0000-0000-0000000000a9', now() - interval '24 day', now() - interval '23 day', now() - interval '22 day')
ON CONFLICT (id) DO NOTHING;

-- ── Báo giá (m29) ──────────────────────────────────────────────────────────
INSERT INTO quotations (id, code, intake_id, customer_name, customer_address, customer_email,
                        customer_phone, customer_tax_code, issue_date, valid_until, vat_rate,
                        subtotal, vat_amount, total, status, note, sent_at, decided_at, created_by) VALUES
 ('00000000-0000-0000-0000-0000001b0001','BG-2026-0021','00000000-0000-0000-0000-000000190002',
  'Công ty TNHH Thủy sản Minh Phú','KCN Khánh An, H. U Minh, Tỉnh Cà Mau','qa@minhphu.com',
  '0290 3612 8','2000103546', current_date - 4, current_date + 26, 8,
  1800000, 144000, 1944000,'sent',NULL, now() - interval '4 day', NULL,'00000000-0000-0000-0000-0000000000a9'),
 ('00000000-0000-0000-0000-0000001b0002','BG-2026-0022','00000000-0000-0000-0000-000000190003',
  'Viện Kiểm nghiệm ATVSTP Quốc gia','65 Phạm Thận Duật, Q. Cầu Giấy, TP. Hà Nội','contact@nifc.gov.vn',
  NULL,'0100112233', current_date - 6, current_date + 24, 8,
  510000, 40800, 550800,'accepted','Khách xác nhận qua email ngày 29/08/2026.',
  now() - interval '6 day', now() - interval '2 day','00000000-0000-0000-0000-0000000000a9')
ON CONFLICT (id) DO NOTHING;

INSERT INTO quotation_items (id, quotation_id, sort_order, sample_name, test_parameter_id,
                             parameter_name, method, unit, quantity, unit_price, amount) VALUES
 ('00000000-0000-0000-0000-0000001b1001','00000000-0000-0000-0000-0000001b0001',1,'Tôm thẻ đông lạnh','00000000-0000-0000-0000-000000180005','Cadimi (Cd)','AOAC 999.11','mg/kg',2,450000,900000),
 ('00000000-0000-0000-0000-0000001b1002','00000000-0000-0000-0000-0000001b0001',2,'Tôm thẻ đông lạnh','00000000-0000-0000-0000-000000180006','Chì (Pb)','AOAC 999.11','mg/kg',2,450000,900000),
 ('00000000-0000-0000-0000-0000001b1003','00000000-0000-0000-0000-0000001b0002',1,'Mẫu nước so sánh','00000000-0000-0000-0000-000000180002','COD','SMEWW 5220C:2017','mg/L',1,250000,250000),
 ('00000000-0000-0000-0000-0000001b1004','00000000-0000-0000-0000-0000001b0002',2,'Mẫu nước so sánh','00000000-0000-0000-0000-000000180003','BOD5','SMEWW 5210B:2017','mg/L',1,280000,280000)
ON CONFLICT (id) DO NOTHING;

COMMIT;
