-- ============================================================================
-- LIMS — Seed dữ liệu demo (mock) để hiển thị trên UI
-- An toàn re-run: dùng ON CONFLICT DO NOTHING theo PK.
-- ID đánh theo khối hex: 00000000-0000-0000-0000-000000<BB>00<NN>
--   BB: 01 customer 02 request 03 sample 04 assignment 05 result
--       06 chemical 07 lot 08 txn 09 document 0a doc_version
--       0b equipment 0c calibration 0d project 0e publication
--       0f mentorship 10 lab_reg 11 teaching 12 community
--       13 competence 14 salary 15 notification 16 overdue_reason
-- Users demo: mật khẩu chung "Lims@1234".
-- ============================================================================
BEGIN;

-- ── Users (a2..a8) — hash của "Lims@1234" ──────────────────────────────────
INSERT INTO users (id, email, password_hash, full_name, department_id, role, status, password_changed_at, created_by) VALUES
 ('00000000-0000-0000-0000-0000000000a2','hoa.tm@lims.local',   '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','TS. Trần Minh Hòa',   '00000000-0000-0000-0000-0000000000d2','leader',    'active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a3','huong.lt@lims.local', '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','KS. Lê Thị Hương',    '00000000-0000-0000-0000-0000000000d2','staff',     'active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a4','nam.pv@lims.local',   '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','CN. Phạm Văn Nam',    '00000000-0000-0000-0000-0000000000d2','staff',     'active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a5','sinh.nt@lims.local',  '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','TS. Nguyễn Thị Sinh', '00000000-0000-0000-0000-0000000000d3','leader',    'active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a6','son.vd@lims.local',   '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','CN. Vũ Đức Sơn',      '00000000-0000-0000-0000-0000000000d3','staff',     'active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a7','ke.dt@lims.local',    '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','CN. Đỗ Thị Kế',       '00000000-0000-0000-0000-0000000000d4','accountant','active', now(), '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000a8','long.hv@lims.local',  '$2b$12$CJ7aBPZ1OtDcvq.trbUbKeDIRRDXelYCwWDtpl/3IsfAgRhBicjOe','KS. Hoàng Văn Long',  '00000000-0000-0000-0000-0000000000d2','staff',     'active', now(), '00000000-0000-0000-0000-0000000000a1')
ON CONFLICT (id) DO NOTHING;

-- Gán trưởng phòng
UPDATE departments SET lead_user_id='00000000-0000-0000-0000-0000000000a1' WHERE id='00000000-0000-0000-0000-0000000000d1' AND lead_user_id IS NULL;
UPDATE departments SET lead_user_id='00000000-0000-0000-0000-0000000000a2' WHERE id='00000000-0000-0000-0000-0000000000d2' AND lead_user_id IS NULL;
UPDATE departments SET lead_user_id='00000000-0000-0000-0000-0000000000a5' WHERE id='00000000-0000-0000-0000-0000000000d3' AND lead_user_id IS NULL;
UPDATE departments SET lead_user_id='00000000-0000-0000-0000-0000000000a7' WHERE id='00000000-0000-0000-0000-0000000000d4' AND lead_user_id IS NULL;

-- ── Customers ──────────────────────────────────────────────────────────────
INSERT INTO customers (id, name, contact, type, note, created_by) VALUES
 ('00000000-0000-0000-0000-000000010001','Công ty CP Dược Hậu Giang','Ms. Lan — 0292 389 0000','organization','Khách hàng thường xuyên, mẫu dược phẩm','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000010002','Viện Kiểm nghiệm ATVSTP Quốc gia','contact@nifc.gov.vn','organization','Hợp tác kiểm nghiệm chéo','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000010003','Nguyễn Văn Khách','0905 123 456','individual','Cá nhân gửi mẫu nước sinh hoạt','00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000010004','Khoa Hóa — Nội bộ','noibo@lims.local','internal','Yêu cầu nội bộ giữa các khoa','00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-000000010005','Công ty TNHH Thủy sản Minh Phú','qa@minhphu.com','organization','Mẫu thủy sản xuất khẩu — kim loại nặng','00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── Test requests ──────────────────────────────────────────────────────────
INSERT INTO test_requests (id, request_code, customer_id, sender_name, department_id, received_by, received_at, note, created_by) VALUES
 ('00000000-0000-0000-0000-000000020001','YC-2026-0001','00000000-0000-0000-0000-000000010001',NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2', now()-interval '8 days', 'Định lượng hoạt chất + độ ẩm 2 mẫu viên nén','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000020002','YC-2026-0002','00000000-0000-0000-0000-000000010002',NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a3', now()-interval '6 days', 'Kiểm nghiệm chéo pH và tạp chất','00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000020003','YC-2026-0003','00000000-0000-0000-0000-000000010005',NULL,'00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5', now()-interval '5 days', 'Vi sinh + định danh vi khuẩn mẫu tôm','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000020004','YC-2026-0004',NULL,'Sở Y tế Cần Thơ','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2', now()-interval '3 days', 'Mẫu nước — chỉ tiêu hóa lý','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000020005','YC-2026-0005','00000000-0000-0000-0000-000000010003',NULL,'00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a6', now()-interval '2 days', 'Mẫu nước sinh hoạt — vi sinh','00000000-0000-0000-0000-0000000000a6'),
 ('00000000-0000-0000-0000-000000020006','YC-2026-0006','00000000-0000-0000-0000-000000010004',NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2', now()-interval '12 days', 'Kim loại nặng — yêu cầu nội bộ','00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- ── Samples ────────────────────────────────────────────────────────────────
INSERT INTO samples (id, sample_code, request_id, department_id, received_by, current_custodian_id, description, received_at, deadline_at, completed_at, status, condition_status, condition_note, created_by) VALUES
 ('00000000-0000-0000-0000-000000030001','SP-2026-0001','00000000-0000-0000-0000-000000020001','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a3','Viên nén Paracetamol 500mg — lô A', now()-interval '8 days', now()+interval '2 days', NULL, 'testing','acceptable',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000030002','SP-2026-0002','00000000-0000-0000-0000-000000020001','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a4','Viên nén Paracetamol 500mg — lô B', now()-interval '8 days', now()-interval '1 days', now()-interval '1 days', 'done','acceptable',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000030003','SP-2026-0003','00000000-0000-0000-0000-000000020002','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a3','Dung dịch mẫu kiểm nghiệm chéo', now()-interval '6 days', now()+interval '4 days', NULL, 'assigned','acceptable',NULL,'00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000030004','SP-2026-0004','00000000-0000-0000-0000-000000020002','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a8','Mẫu bột — tạp chất', now()-interval '6 days', now()-interval '2 days', NULL, 'overdue','acceptable',NULL,'00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000030005','SP-2026-0005','00000000-0000-0000-0000-000000020003','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000a6','Mẫu tôm đông lạnh — vi sinh tổng số', now()-interval '5 days', now()+interval '3 days', NULL, 'testing','acceptable',NULL,'00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000030006','SP-2026-0006','00000000-0000-0000-0000-000000020003','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000a5','Mẫu tôm — định danh vi khuẩn', now()-interval '5 days', now()-interval '6 hours', now()-interval '6 hours', 'done','acceptable',NULL,'00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000030007','SP-2026-0007','00000000-0000-0000-0000-000000020004','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a4','Mẫu nước máy — hóa lý', now()-interval '3 days', now()+interval '5 days', NULL, 'received','acceptable',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000030008','SP-2026-0008','00000000-0000-0000-0000-000000020005','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a6','00000000-0000-0000-0000-0000000000a6','Mẫu nước sinh hoạt — bao bì rò rỉ', now()-interval '2 days', now()+interval '6 days', NULL, 'returned','not_acceptable','Bao bì rò rỉ, thể tích không đủ — trả lại khách bổ sung','00000000-0000-0000-0000-0000000000a6'),
 ('00000000-0000-0000-0000-000000030009','SP-2026-0009','00000000-0000-0000-0000-000000020006','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a3','Mẫu cá — kim loại nặng (Pb, Cd)', now()-interval '12 days', now()-interval '4 days', now()-interval '4 days', 'done','acceptable',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-00000003000a','SP-2026-0010','00000000-0000-0000-0000-000000020001','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000a8','Viên nén Paracetamol — mẫu lưu', now()-interval '8 days', now()+interval '1 days', NULL, 'assigned','acceptable',NULL,'00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- ── Sample assignments ─────────────────────────────────────────────────────
INSERT INTO sample_assignments (id, sample_id, assigned_to, assigned_by, part_name, status, assigned_at, created_by) VALUES
 ('00000000-0000-0000-0000-000000040001','00000000-0000-0000-0000-000000030001','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a2','Định lượng hoạt chất (HPLC)','in_progress', now()-interval '7 days','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000040002','00000000-0000-0000-0000-000000030002','00000000-0000-0000-0000-0000000000a4','00000000-0000-0000-0000-0000000000a2','Độ ẩm','approved', now()-interval '7 days','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000040003','00000000-0000-0000-0000-000000030003','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a2','pH','assigned', now()-interval '5 days','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000040004','00000000-0000-0000-0000-000000030005','00000000-0000-0000-0000-0000000000a6','00000000-0000-0000-0000-0000000000a5','Vi sinh tổng số','in_progress', now()-interval '4 days','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000040005','00000000-0000-0000-0000-000000030006','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000a5','Định danh vi khuẩn','approved', now()-interval '5 days','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000040006','00000000-0000-0000-0000-000000030009','00000000-0000-0000-0000-0000000000a3','00000000-0000-0000-0000-0000000000a2','Kim loại nặng (AAS)','approved', now()-interval '11 days','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000040007','00000000-0000-0000-0000-00000003000a','00000000-0000-0000-0000-0000000000a8','00000000-0000-0000-0000-0000000000a2','Định lượng','assigned', now()-interval '7 days','00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- ── Sample results (cho các assignment đã duyệt) ──────────────────────────
INSERT INTO sample_results (id, assignment_id, version, result_data, note, entered_by, entered_at, approved_by, approved_at, is_current) VALUES
 ('00000000-0000-0000-0000-000000050001','00000000-0000-0000-0000-000000040002',1,'{"do_am_percent": 4.2, "gioi_han": "≤ 5.0", "dat": true}','Đạt yêu cầu','00000000-0000-0000-0000-0000000000a4', now()-interval '2 days','00000000-0000-0000-0000-0000000000a2', now()-interval '1 days', true),
 ('00000000-0000-0000-0000-000000050002','00000000-0000-0000-0000-000000040005',1,'{"vi_khuan": "Vibrio parahaemolyticus", "ket_qua": "Phát hiện", "dat": false}','Phát hiện vi khuẩn gây bệnh','00000000-0000-0000-0000-0000000000a5', now()-interval '12 hours','00000000-0000-0000-0000-0000000000a5', now()-interval '6 hours', true),
 ('00000000-0000-0000-0000-000000050003','00000000-0000-0000-0000-000000040006',1,'{"pb_ppm": 0.08, "cd_ppm": 0.01, "gioi_han_pb": "≤ 0.10", "dat": true}','Trong giới hạn cho phép','00000000-0000-0000-0000-0000000000a3', now()-interval '5 days','00000000-0000-0000-0000-0000000000a2', now()-interval '4 days', true)
ON CONFLICT (id) DO NOTHING;

-- ── Chemicals ──────────────────────────────────────────────────────────────
INSERT INTO chemicals (id, name, cas_no, manufacturer, base_unit, measurement_group, hazard_code, reorder_threshold, department_id, status, created_by) VALUES
 ('00000000-0000-0000-0000-000000060001','Natri hydroxit (NaOH)','1310-73-2','Merck','g','mass','GHS05', 500,   '00000000-0000-0000-0000-0000000000d2','active','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000060002','Axit clohydric (HCl) 37%','7647-01-0','Merck','mL','volume','GHS05,GHS07', 1000, '00000000-0000-0000-0000-0000000000d2','active','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000060003','Ethanol tuyệt đối','64-17-5','Xilong','mL','volume','GHS02', 2000, '00000000-0000-0000-0000-0000000000d2','active','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000060004','Methanol (HPLC grade)','67-56-1','Merck','mL','volume','GHS02,GHS06', 1000, '00000000-0000-0000-0000-0000000000d2','active','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000060005','Thạch dinh dưỡng (Nutrient Agar)',NULL,'HiMedia','g','mass',NULL, 300, '00000000-0000-0000-0000-0000000000d3','active','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000060006','Kali dicromat (K2Cr2O7)','7778-50-9','Merck','g','mass','GHS03,GHS08', 200, '00000000-0000-0000-0000-0000000000d2','active','00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- Ẩn 2 chemical rác cũ (test) khỏi danh sách active
UPDATE chemicals SET status='inactive' WHERE name IN ('FileProxy Test','DbgChem 0b04b37e') AND status='active';

-- ── Chemical lots ──────────────────────────────────────────────────────────
INSERT INTO chemical_lots (id, chemical_id, lot_no, qty_base, unit_price, price_unit, currency, received_at, expiry_date, recheck_date, recheck_result, is_expired, created_by) VALUES
 ('00000000-0000-0000-0000-000000070001','00000000-0000-0000-0000-000000060001','NAOH-2025-01', 4950, 120000,'kg','VND',(now()-interval '200 days')::date,(now()+interval '400 days')::date,NULL,NULL,false,'00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000070002','00000000-0000-0000-0000-000000060002','HCL-2026-01', 4000, 85000,'L','VND',(now()-interval '60 days')::date,(now()+interval '20 days')::date,NULL,NULL,false,'00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000070003','00000000-0000-0000-0000-000000060003','ETOH-2026-03', 8000, 60000,'L','VND',(now()-interval '90 days')::date,(now()+interval '300 days')::date,NULL,NULL,false,'00000000-0000-0000-0000-0000000000a4'),
 ('00000000-0000-0000-0000-000000070004','00000000-0000-0000-0000-000000060004','MEOH-2025-11', 2500, 350000,'L','VND',(now()-interval '150 days')::date,(now()+interval '150 days')::date,(now()+interval '30 days')::date,'pass',false,'00000000-0000-0000-0000-0000000000a4'),
 ('00000000-0000-0000-0000-000000070005','00000000-0000-0000-0000-000000060005','AGAR-2026-02', 3000, 900000,'kg','VND',(now()-interval '40 days')::date,(now()+interval '500 days')::date,NULL,NULL,false,'00000000-0000-0000-0000-0000000000a6'),
 ('00000000-0000-0000-0000-000000070006','00000000-0000-0000-0000-000000060006','K2CR2O7-2024', 800, 500000,'kg','VND',(now()-interval '400 days')::date,(now()-interval '10 days')::date,NULL,NULL,true,'00000000-0000-0000-0000-0000000000a3')
ON CONFLICT (id) DO NOTHING;

-- ── Chemical transactions ──────────────────────────────────────────────────
INSERT INTO chemical_transactions (id, lot_id, type, qty_base, base_unit, qty_input, input_unit, balance_after, unit_price, price_unit, currency, ref_sample_id, note, by_user, at) VALUES
 ('00000000-0000-0000-0000-000000080001','00000000-0000-0000-0000-000000070001','in',  5000,'g',   5,'kg', 5000, 120000,'kg','VND',NULL,'Nhập kho lô NaOH','00000000-0000-0000-0000-0000000000a3', now()-interval '200 days'),
 ('00000000-0000-0000-0000-000000080002','00000000-0000-0000-0000-000000070001','out',   50,'g',  50,'g',  4950, NULL,NULL,NULL,'00000000-0000-0000-0000-000000030001','Xuất dùng cho mẫu SP-2026-0001','00000000-0000-0000-0000-0000000000a3', now()-interval '6 days'),
 ('00000000-0000-0000-0000-000000080003','00000000-0000-0000-0000-000000070003','in',  8000,'mL',  8,'L',  8000, 60000,'L','VND',NULL,'Nhập kho lô Ethanol','00000000-0000-0000-0000-0000000000a4', now()-interval '90 days'),
 ('00000000-0000-0000-0000-000000080004','00000000-0000-0000-0000-000000070006','in',   800,'g', 800,'g',   800, 500000,'kg','VND',NULL,'Nhập kho lô K2Cr2O7','00000000-0000-0000-0000-0000000000a3', now()-interval '400 days')
ON CONFLICT (id) DO NOTHING;

-- ── Documents (current_version_id set sau khi có version) ──────────────────
INSERT INTO documents (id, code, title, type, department_id, security_level, status, current_version_id, created_by) VALUES
 ('00000000-0000-0000-0000-000000090001','SOP-HOA-001','SOP Định lượng hoạt chất bằng HPLC','sop','00000000-0000-0000-0000-0000000000d2','internal','active',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000090002','SOP-HOA-002','SOP Xác định độ ẩm bằng phương pháp sấy','sop','00000000-0000-0000-0000-0000000000d2','internal','active',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000090003','QT-QLCL-001','Quy trình kiểm soát tài liệu ISO 17025','process','00000000-0000-0000-0000-0000000000d1','internal','active',NULL,'00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-000000090004','BM-HOA-005','Biểu mẫu phiếu kết quả thử nghiệm','form','00000000-0000-0000-0000-0000000000d2','internal','active',NULL,'00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-000000090005','SOP-SINH-001','SOP Định danh vi khuẩn gây bệnh','sop','00000000-0000-0000-0000-0000000000d3','restricted','active',NULL,'00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000090006','HD-ATSH-001','Hướng dẫn an toàn sinh học cấp 2','guide','00000000-0000-0000-0000-0000000000d3','internal','active',NULL,'00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── Document versions ──────────────────────────────────────────────────────
-- doc1: v1 obsolete + v2 approved (hiện hành)
INSERT INTO document_versions (id, document_id, version_no, change_note, status, created_by, created_at, submitted_by, submitted_at, reviewed_by, reviewed_at, approved_by, approved_at) VALUES
 ('00000000-0000-0000-0000-0000000a0001','00000000-0000-0000-0000-000000090001',1,'Ban hành lần đầu','obsolete','00000000-0000-0000-0000-0000000000a2', now()-interval '400 days','00000000-0000-0000-0000-0000000000a2', now()-interval '395 days','00000000-0000-0000-0000-0000000000a2', now()-interval '392 days','00000000-0000-0000-0000-0000000000a1', now()-interval '390 days'),
 ('00000000-0000-0000-0000-0000000a0002','00000000-0000-0000-0000-000000090001',2,'Cập nhật điều kiện sắc ký','approved','00000000-0000-0000-0000-0000000000a2', now()-interval '90 days','00000000-0000-0000-0000-0000000000a2', now()-interval '85 days','00000000-0000-0000-0000-0000000000a2', now()-interval '82 days','00000000-0000-0000-0000-0000000000a1', now()-interval '80 days'),
 ('00000000-0000-0000-0000-0000000a0003','00000000-0000-0000-0000-000000090002',1,'Ban hành lần đầu','approved','00000000-0000-0000-0000-0000000000a2', now()-interval '120 days','00000000-0000-0000-0000-0000000000a2', now()-interval '118 days','00000000-0000-0000-0000-0000000000a2', now()-interval '116 days','00000000-0000-0000-0000-0000000000a1', now()-interval '115 days'),
 ('00000000-0000-0000-0000-0000000a0004','00000000-0000-0000-0000-000000090003',1,'Ban hành lần đầu','approved','00000000-0000-0000-0000-0000000000a1', now()-interval '300 days','00000000-0000-0000-0000-0000000000a1', now()-interval '298 days','00000000-0000-0000-0000-0000000000a1', now()-interval '296 days','00000000-0000-0000-0000-0000000000a1', now()-interval '295 days'),
 ('00000000-0000-0000-0000-0000000a0005','00000000-0000-0000-0000-000000090004',1,'Ban hành lần đầu','approved','00000000-0000-0000-0000-0000000000a3', now()-interval '60 days','00000000-0000-0000-0000-0000000000a3', now()-interval '58 days','00000000-0000-0000-0000-0000000000a2', now()-interval '56 days','00000000-0000-0000-0000-0000000000a1', now()-interval '55 days'),
 -- doc5: đang chờ duyệt (review)
 ('00000000-0000-0000-0000-0000000a0006','00000000-0000-0000-0000-000000090005',1,'Bản thảo chờ duyệt','review','00000000-0000-0000-0000-0000000000a5', now()-interval '10 days','00000000-0000-0000-0000-0000000000a5', now()-interval '8 days',NULL,NULL,NULL,NULL),
 -- doc6: draft
 ('00000000-0000-0000-0000-0000000a0007','00000000-0000-0000-0000-000000090006',1,'Đang soạn thảo','draft','00000000-0000-0000-0000-0000000000a5', now()-interval '3 days',NULL,NULL,NULL,NULL,NULL,NULL)
ON CONFLICT (id) DO NOTHING;

-- Trỏ current_version_id cho các document có bản approved
UPDATE documents SET current_version_id='00000000-0000-0000-0000-0000000a0002' WHERE id='00000000-0000-0000-0000-000000090001';
UPDATE documents SET current_version_id='00000000-0000-0000-0000-0000000a0003' WHERE id='00000000-0000-0000-0000-000000090002';
UPDATE documents SET current_version_id='00000000-0000-0000-0000-0000000a0004' WHERE id='00000000-0000-0000-0000-000000090003';
UPDATE documents SET current_version_id='00000000-0000-0000-0000-0000000a0005' WHERE id='00000000-0000-0000-0000-000000090004';

-- ── Equipments ─────────────────────────────────────────────────────────────
INSERT INTO equipments (id, code, name, location, department_id, responsible_user_id, purchase_date, status, calibration_cycle_value, calibration_cycle_unit, next_due_date, note, created_by) VALUES
 ('00000000-0000-0000-0000-0000000b0001','TB-HOA-001','Cân phân tích Sartorius BSA224S','Phòng cân — Lab Hóa','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a3',(now()-interval '3 years')::date,'active',12,'month',(now()+interval '200 days')::date,'Độ chính xác 0.1mg','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000b0002','TB-HOA-002','Máy quang phổ UV-Vis Shimadzu','Lab Hóa — bàn 3','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2',(now()-interval '4 years')::date,'active',12,'month',(now()+interval '20 days')::date,'Sắp đến hạn hiệu chuẩn','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000b0003','TB-HOA-003','Tủ sấy Memmert UN55','Lab Hóa','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a4',(now()-interval '2 years')::date,'active',24,'month',(now()+interval '350 days')::date,NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000b0004','TB-SINH-001','Nồi hấp tiệt trùng Hirayama','Lab Sinh','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a6',(now()-interval '5 years')::date,'active',12,'month',(now()-interval '5 days')::date,'ĐÃ QUÁ HẠN hiệu chuẩn','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000b0005','TB-SINH-002','Kính hiển vi Olympus CX23','Lab Sinh','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5',(now()-interval '1 years')::date,'maintenance',NULL,NULL,NULL,'Đang bảo trì đèn','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000b0006','TB-HOA-004','Máy ly tâm Hettich EBA 200','Lab Hóa','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a8',(now()-interval '2 years')::date,'active',12,'month',(now()+interval '265 days')::date,NULL,'00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- ── Calibration records (immutable — chỉ INSERT) ──────────────────────────
INSERT INTO calibration_records (id, equipment_id, calibrated_at, provider, result, next_due_date, note, created_by, created_at) VALUES
 ('00000000-0000-0000-0000-0000000c0001','00000000-0000-0000-0000-0000000b0001',(now()-interval '165 days')::date,'QUATEST 3','pass',(now()+interval '200 days')::date,'Đạt toàn bộ điểm chuẩn','00000000-0000-0000-0000-0000000000a2', now()-interval '165 days'),
 ('00000000-0000-0000-0000-0000000c0002','00000000-0000-0000-0000-0000000b0002',(now()-interval '345 days')::date,'QUATEST 3','pass',(now()+interval '20 days')::date,NULL,'00000000-0000-0000-0000-0000000000a2', now()-interval '345 days'),
 ('00000000-0000-0000-0000-0000000c0003','00000000-0000-0000-0000-0000000b0004',(now()-interval '370 days')::date,'Trung tâm KĐ 2','pass',(now()-interval '5 days')::date,'Cần đặt lịch hiệu chuẩn lại','00000000-0000-0000-0000-0000000000a5', now()-interval '370 days'),
 ('00000000-0000-0000-0000-0000000c0004','00000000-0000-0000-0000-0000000b0006',(now()-interval '100 days')::date,'QUATEST 3','pass',(now()+interval '265 days')::date,NULL,'00000000-0000-0000-0000-0000000000a2', now()-interval '100 days')
ON CONFLICT (id) DO NOTHING;

-- ── Research projects ──────────────────────────────────────────────────────
INSERT INTO research_projects (id, code, title, level, lead_user_id, department_id, start_date, end_date, status, created_by) VALUES
 ('00000000-0000-0000-0000-0000000d0001','DT-2025-01','Nghiên cứu quy trình định lượng hoạt chất trong dược liệu bằng HPLC','university','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000d2',(now()-interval '300 days')::date,(now()+interval '120 days')::date,'ongoing','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000d0002','DT-2024-05','Phân lập vi khuẩn probiotic từ thực phẩm lên men truyền thống','ministry','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000d3',(now()-interval '700 days')::date,(now()-interval '100 days')::date,'completed','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000d0003','DT-2026-02','Ứng dụng cảm biến sinh học phát hiện dư lượng kháng sinh trong thủy sản','national','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000d3',(now()-interval '120 days')::date,(now()+interval '600 days')::date,'ongoing','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000d0004','DT-2023-09','Đánh giá kim loại nặng trong thủy sản vùng ĐBSCL','province','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000d2',(now()-interval '900 days')::date,(now()-interval '300 days')::date,'accepted','00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

INSERT INTO project_members (project_id, user_id, role_in_project) VALUES
 ('00000000-0000-0000-0000-0000000d0001','00000000-0000-0000-0000-0000000000a2','lead'),
 ('00000000-0000-0000-0000-0000000d0001','00000000-0000-0000-0000-0000000000a3','member'),
 ('00000000-0000-0000-0000-0000000d0001','00000000-0000-0000-0000-0000000000a4','member'),
 ('00000000-0000-0000-0000-0000000d0002','00000000-0000-0000-0000-0000000000a5','lead'),
 ('00000000-0000-0000-0000-0000000d0002','00000000-0000-0000-0000-0000000000a6','member'),
 ('00000000-0000-0000-0000-0000000d0003','00000000-0000-0000-0000-0000000000a5','lead'),
 ('00000000-0000-0000-0000-0000000d0003','00000000-0000-0000-0000-0000000000a6','member'),
 ('00000000-0000-0000-0000-0000000d0003','00000000-0000-0000-0000-0000000000a2','member'),
 ('00000000-0000-0000-0000-0000000d0004','00000000-0000-0000-0000-0000000000a2','lead'),
 ('00000000-0000-0000-0000-0000000d0004','00000000-0000-0000-0000-0000000000a8','member')
ON CONFLICT (project_id, user_id) DO NOTHING;

-- ── Publications ───────────────────────────────────────────────────────────
INSERT INTO publications (id, title, journal, year, doi, category, type, patent_no, issuing_authority, department_id, created_by) VALUES
 ('00000000-0000-0000-0000-0000000e0001','A validated HPLC method for simultaneous determination of active compounds in herbal tablets','Journal of Pharmaceutical Analysis',2025,'10.1016/j.jpha.2025.01.012','isi_q1','paper',NULL,NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000e0002','Isolation and characterization of probiotic bacteria from fermented foods','Food Microbiology',2024,'10.1016/j.fm.2024.104321','isi_q2','paper',NULL,NULL,'00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000e0003','Heavy metal contamination in aquatic products of the Mekong Delta','Chemosphere',2023,'10.1016/j.chemosphere.2023.138777','isi_q1','paper',NULL,NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000e0004','Xây dựng quy trình xác định độ ẩm dược liệu bằng phương pháp sấy','Tạp chí Phân tích Hóa Lý Sinh',2025,NULL,'domestic','paper',NULL,NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a3'),
 ('00000000-0000-0000-0000-0000000e0005','Quy trình sản xuất chế phẩm probiotic từ vi khuẩn phân lập',NULL,2024,NULL,NULL,'patent','VN1-2024-01234','Cục Sở hữu trí tuệ','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

INSERT INTO publication_authors (publication_id, author_order, user_id, external_name, is_corresponding) VALUES
 ('00000000-0000-0000-0000-0000000e0001',1,'00000000-0000-0000-0000-0000000000a2',NULL,true),
 ('00000000-0000-0000-0000-0000000e0001',2,'00000000-0000-0000-0000-0000000000a3',NULL,false),
 ('00000000-0000-0000-0000-0000000e0002',1,'00000000-0000-0000-0000-0000000000a5',NULL,true),
 ('00000000-0000-0000-0000-0000000e0002',2,'00000000-0000-0000-0000-0000000000a6',NULL,false),
 ('00000000-0000-0000-0000-0000000e0002',3,NULL,'Prof. K. Yamamoto',false),
 ('00000000-0000-0000-0000-0000000e0003',1,'00000000-0000-0000-0000-0000000000a2',NULL,false),
 ('00000000-0000-0000-0000-0000000e0003',2,'00000000-0000-0000-0000-0000000000a8',NULL,true),
 ('00000000-0000-0000-0000-0000000e0004',1,'00000000-0000-0000-0000-0000000000a3',NULL,true),
 ('00000000-0000-0000-0000-0000000e0005',1,'00000000-0000-0000-0000-0000000000a5',NULL,true),
 ('00000000-0000-0000-0000-0000000e0005',2,'00000000-0000-0000-0000-0000000000a6',NULL,false)
ON CONFLICT (publication_id, author_order) DO NOTHING;

-- ── Student mentorships ────────────────────────────────────────────────────
INSERT INTO student_mentorships (id, mentor_id, student_name, topic, year, type, department_id, created_by) VALUES
 ('00000000-0000-0000-0000-0000000f0001','00000000-0000-0000-0000-0000000000a2','Nguyễn Thị Lan','Định lượng paracetamol trong viên nén bằng HPLC',2025,'thesis_bachelor','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000f0002','00000000-0000-0000-0000-0000000000a5','Trần Văn Bình','Khảo sát hệ vi sinh trong sản phẩm lên men',2025,'thesis_master','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-0000000f0003','00000000-0000-0000-0000-0000000000a2','Lê Hoàng Phúc','Tối ưu điều kiện chiết hoạt chất từ dược liệu',2024,'student_research','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000f0004','00000000-0000-0000-0000-0000000000a5','Phạm Thu Trang','Cảm biến sinh học phát hiện kháng sinh',2026,'thesis_phd','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── Lab registrations ──────────────────────────────────────────────────────
INSERT INTO lab_registrations (id, student_name, mentor_id, registered_at, registered_from, registered_to, purpose, status, approved_by, approved_at, department_id, created_by) VALUES
 ('00000000-0000-0000-0000-000000100001','Đặng Minh Quân','00000000-0000-0000-0000-0000000000a2',(now()-interval '2 days')::date,(now()+interval '5 days')::date,(now()+interval '40 days')::date,'Thực tập phân tích HPLC','pending',NULL,NULL,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000100002','Vũ Thị Ngọc','00000000-0000-0000-0000-0000000000a5',(now()-interval '20 days')::date,(now()-interval '15 days')::date,(now()+interval '30 days')::date,'Nghiên cứu vi sinh cho luận văn','approved','00000000-0000-0000-0000-0000000000a5', now()-interval '18 days','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000100003','Hồ Văn Tài','00000000-0000-0000-0000-0000000000a2',(now()-interval '25 days')::date,(now()-interval '20 days')::date,(now()-interval '5 days')::date,'Đăng ký trùng lịch thiết bị','rejected','00000000-0000-0000-0000-0000000000a1', now()-interval '23 days','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2')
ON CONFLICT (id) DO NOTHING;

-- ── Teaching courses ───────────────────────────────────────────────────────
INSERT INTO teaching_courses (id, user_id, course_name, semester, year, department_id, created_by) VALUES
 ('00000000-0000-0000-0000-000000110001','00000000-0000-0000-0000-0000000000a2','Hóa phân tích','HK1',2025,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000110002','00000000-0000-0000-0000-0000000000a2','Thực hành Hóa phân tích','HK1',2025,'00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000110003','00000000-0000-0000-0000-0000000000a5','Vi sinh vật học','HK2',2025,'00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5'),
 ('00000000-0000-0000-0000-000000110004','00000000-0000-0000-0000-0000000000a5','Công nghệ vi sinh','HK1',2026,'00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── Community services ─────────────────────────────────────────────────────
INSERT INTO community_services (id, content, performed_at, host, performer_user_id, department_id, created_by) VALUES
 ('00000000-0000-0000-0000-000000120001','Tư vấn kiểm nghiệm chất lượng nước sinh hoạt cho các trường học vùng sâu',(now()-interval '60 days')::date,'Phòng GD&ĐT huyện','00000000-0000-0000-0000-0000000000a2','00000000-0000-0000-0000-0000000000d2','00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000120002','Tập huấn an toàn sinh học phòng thí nghiệm cho giáo viên THPT',(now()-interval '120 days')::date,'Sở KH&CN','00000000-0000-0000-0000-0000000000a5','00000000-0000-0000-0000-0000000000d3','00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── HR profiles (phải trước competences/salary_history — FK tới hr_profiles) ──
INSERT INTO hr_profiles (user_id, job_title, hired_date, phone, "position", contract_type, contract_signed_date, contract_end_date, salary_grade, salary_coefficient, base_salary_amount, salary_cycle_years, last_salary_raise_date, next_salary_raise_date, created_by) VALUES
 ('00000000-0000-0000-0000-0000000000a2','Trưởng phòng Thí nghiệm Hóa','2015-10-01','0905 111 222','Trưởng phòng','indefinite','2015-10-01',NULL,'A1',3.99,2340000,3,(now()-interval '400 days')::date,(now()+interval '695 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a3','Kiểm nghiệm viên','2020-03-01','0905 111 333','Nhân viên','fixed_term','2024-03-01',(now()+interval '90 days')::date,'A1',2.67,2340000,3,(now()-interval '200 days')::date,(now()+interval '895 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a4','Kiểm nghiệm viên','2021-06-01','0905 111 444','Nhân viên','fixed_term','2024-06-01',(now()+interval '25 days')::date,'A1',2.34,2340000,3,(now()-interval '100 days')::date,(now()+interval '995 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a5','Trưởng phòng Thí nghiệm Sinh','2016-08-01','0905 222 555','Trưởng phòng','civil_servant','2016-08-01',NULL,'A2',4.32,2340000,3,(now()-interval '200 days')::date,(now()+interval '895 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a6','Kỹ thuật viên vi sinh','2022-01-15','0905 222 666','Nhân viên','fixed_term','2025-01-15',(now()+interval '200 days')::date,'A1',2.34,2340000,3,NULL,(now()+interval '600 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a7','Kế toán viên','2019-04-01','0905 333 777','Nhân viên','indefinite','2019-04-01',NULL,'A1',3.00,2340000,3,(now()-interval '300 days')::date,(now()+interval '795 days')::date,'00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-0000000000a8','Kiểm nghiệm viên','2023-09-01','0905 111 888','Nhân viên','probation','2026-06-01',(now()+interval '5 days')::date,'A1',2.34,2340000,3,NULL,(now()+interval '1000 days')::date,'00000000-0000-0000-0000-0000000000a7')
ON CONFLICT (user_id) DO NOTHING;

-- ── Competences (sau hr_profiles — FK fk_comp_profile) ────────────────────
INSERT INTO competences (id, user_id, kind, title, issuer, issued_date, expiry_date, scope_detail, authorized_by, created_by) VALUES
 ('00000000-0000-0000-0000-000000130001','00000000-0000-0000-0000-0000000000a2','degree','Tiến sĩ Hóa phân tích','ĐH Khoa học Tự nhiên','2015-09-01',NULL,NULL,NULL,'00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-000000130002','00000000-0000-0000-0000-0000000000a2','authorization','Phê duyệt kết quả thử nghiệm Hóa','Ban Giám đốc','2022-01-01',NULL,'Toàn bộ phép thử phòng Hóa','00000000-0000-0000-0000-0000000000a1','00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-000000130003','00000000-0000-0000-0000-0000000000a5','degree','Tiến sĩ Vi sinh vật học','ĐH Cần Thơ','2016-06-01',NULL,NULL,NULL,'00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-000000130004','00000000-0000-0000-0000-0000000000a3','certificate','Chứng chỉ vận hành HPLC','QUATEST 3','2022-03-15','2027-03-15','Sắc ký lỏng hiệu năng cao',NULL,'00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-000000130005','00000000-0000-0000-0000-0000000000a6','certificate','An toàn sinh học cấp 2','Viện Pasteur','2023-05-01',(now()+interval '60 days')::date,NULL,NULL,'00000000-0000-0000-0000-0000000000a5')
ON CONFLICT (id) DO NOTHING;

-- ── Salary history ─────────────────────────────────────────────────────────
INSERT INTO salary_history (id, user_id, old_grade, old_coefficient, old_base_amount, new_grade, new_coefficient, new_base_amount, raise_date, note, by_user) VALUES
 ('00000000-0000-0000-0000-000000140001','00000000-0000-0000-0000-0000000000a2','A1',3.66,2340000,'A1',3.99,2340000,(now()-interval '400 days')::date,'Nâng bậc định kỳ','00000000-0000-0000-0000-0000000000a7'),
 ('00000000-0000-0000-0000-000000140002','00000000-0000-0000-0000-0000000000a5','A2',3.99,2340000,'A2',4.32,2340000,(now()-interval '200 days')::date,'Nâng bậc định kỳ','00000000-0000-0000-0000-0000000000a7')
ON CONFLICT (id) DO NOTHING;

-- ── Notifications ──────────────────────────────────────────────────────────
INSERT INTO notifications (id, user_id, type, title, body, ref_type, ref_id, read_at) VALUES
 ('00000000-0000-0000-0000-000000150001','00000000-0000-0000-0000-0000000000a1','SAMPLE_OVERDUE','Mẫu SP-2026-0004 đã quá hạn','Mẫu thuộc yêu cầu YC-2026-0002 đã quá hạn trả kết quả.','sample','00000000-0000-0000-0000-000000030004',NULL),
 ('00000000-0000-0000-0000-000000150002','00000000-0000-0000-0000-0000000000a2','CALIBRATION_DUE','Thiết bị TB-HOA-002 sắp đến hạn hiệu chuẩn','Máy quang phổ UV-Vis còn 20 ngày đến hạn hiệu chuẩn.','equipment','00000000-0000-0000-0000-0000000b0002',NULL),
 ('00000000-0000-0000-0000-000000150003','00000000-0000-0000-0000-0000000000a2','CHEM_EXPIRY','Lô hóa chất HCL-2026-01 sắp hết hạn','Lô HCl 37% còn 20 ngày đến hạn sử dụng.','chemical','00000000-0000-0000-0000-000000070002',NULL),
 ('00000000-0000-0000-0000-000000150004','00000000-0000-0000-0000-0000000000a7','CONTRACT_EXPIRY','Hợp đồng của KS. Hoàng Văn Long sắp hết hạn','Hợp đồng thử việc còn 5 ngày đến hạn — cần xử lý gia hạn.','hr_profile','00000000-0000-0000-0000-0000000000a8',NULL),
 ('00000000-0000-0000-0000-000000150005','00000000-0000-0000-0000-0000000000a1','SYSTEM','Chào mừng đến với LIMS','Dữ liệu demo đã được nạp để trình diễn.',NULL,NULL, now()-interval '1 days')
ON CONFLICT (id) DO NOTHING;

-- ── Overdue reason (cho mẫu quá hạn) ──────────────────────────────────────
INSERT INTO overdue_reasons (id, sample_id, reason, by_user, at) VALUES
 ('00000000-0000-0000-0000-000000160001','00000000-0000-0000-0000-000000030004','Chờ khách hàng bổ sung thông tin mẫu và điều kiện bảo quản','00000000-0000-0000-0000-0000000000a2', now()-interval '1 days')
ON CONFLICT (id) DO NOTHING;

COMMIT;
