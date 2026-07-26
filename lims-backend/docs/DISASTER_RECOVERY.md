# Disaster Recovery & Backup Runbook — LIMS Backend

Phạm vi: Postgres (dữ liệu nghiệp vụ + audit trail ISO17025) và MinIO (file đính kèm:
CoA/MSDS/tài liệu/minh chứng VILAS/raw data). Redis là cache/lockout — **không cần backup**
(tái tạo được). Đây là tài liệu vận hành (PRODUCTION_READINESS_REVIEW Phase D5).

> Mục tiêu khuyến nghị: **RPO ≤ 24h** (mất tối đa 1 ngày dữ liệu), **RTO ≤ 2h** (khôi phục
> trong 2 giờ). Với hệ thống ISO17025, audit_logs là append-only và KHÔNG được mất — cân
> nhắc RPO ngắn hơn (WAL archiving / PITR) nếu khối lượng cho phép.

---

## 1. Backup Postgres

### 1.1 Sao lưu định kỳ (logic dump — đủ cho RPO 24h)
```bash
# Chạy hằng ngày (cron trên host, KHÔNG trong container app):
docker exec lims-postgres pg_dump -U lims -d lims -F c -f /tmp/lims-$(date +%F).dump
docker cp lims-postgres:/tmp/lims-$(date +%F).dump ./backups/
# Đẩy ./backups/ lên lưu trữ off-site (S3/MinIO khác host) + mã hoá at-rest.
```
- `-F c` = custom format (nén, restore chọn lọc được).
- Giữ tối thiểu 30 bản ngày + 12 bản tháng (tuân thủ lưu hồ sơ).
- **Kiểm chứng**: định kỳ (hàng tháng) restore thử vào DB tạm và chạy `alembic current` +
  vài truy vấn đếm — backup KHÔNG kiểm chứng = không có backup.

### 1.2 RPO ngắn (tùy chọn — PITR bằng WAL archiving)
Bật `archive_mode=on` + `archive_command` đẩy WAL lên off-site; kết hợp base backup
(`pg_basebackup`) → khôi phục tới thời điểm bất kỳ (point-in-time). Cần khi mất < 24h dữ
liệu là không chấp nhận được.

## 2. Backup MinIO
```bash
# Dùng mc mirror sang bucket/host off-site (chạy hằng ngày):
mc mirror --overwrite local/lims-attachments offsite/lims-attachments-backup
```
- File là **immutable** sau upload (key có UUID prefix) → mirror tăng dần rẻ.
- Đảm bảo versioning bật ở bucket đích để chống ghi đè/xoá nhầm.

---

## 3. Khôi phục (Restore)

### 3.1 Postgres
```bash
# 1) Dừng app để không ghi vào DB đang restore:
docker compose -f docker-compose.prod.yml stop lims-api
# 2) Tạo DB trống (hoặc drop+create):
docker exec -i lims-postgres psql -U lims -c "DROP DATABASE IF EXISTS lims; CREATE DATABASE lims;"
# 3) Restore:
docker cp ./backups/lims-YYYY-MM-DD.dump lims-postgres:/tmp/restore.dump
docker exec lims-postgres pg_restore -U lims -d lims --clean --if-exists /tmp/restore.dump
# 4) Xác minh schema đúng version:
docker exec lims-postgres psql -U lims -d lims -c "SELECT version_num FROM alembic_version;"
# 5) Khởi động lại app (migrate service sẽ no-op nếu đã ở head):
docker compose -f docker-compose.prod.yml up -d
```

### 3.2 MinIO
```bash
mc mirror --overwrite offsite/lims-attachments-backup local/lims-attachments
```
> LƯU Ý nhất quán: nếu restore Postgres về thời điểm T nhưng MinIO có file mới hơn T,
> DB sẽ tham chiếu thiếu/thừa file. Ưu tiên restore cả hai về cùng mốc; file thiếu chỉ
> ảnh hưởng tải xuống (app trả 404/503, không sập).

---

## 4. Rollback migration

- Mỗi migration (trừ 2 migration merge demo-data **cố ý non-reversible**:
  `m14_cleanup_forms`, `m15_fix_att_check`) đều có `downgrade()` thực thi được:
  ```bash
  docker exec lims-api alembic downgrade -1   # lùi 1 bước
  ```
- **Trước mọi deploy có migration rủi ro**: chụp `pg_dump` ngay trước khi chạy migrate
  (service `migrate` trong compose chạy trước `lims-api`). Nếu migrate hỏng giữa chừng,
  advisory-lock + transactional DDL của alembic đảm bảo rollback tự động của bước đang chạy;
  khôi phục toàn cục dùng dump ở §3.1.
- Với migration MERGE dữ liệu thật trong tương lai: snapshot các dòng bị gộp vào bảng
  archive TRƯỚC khi xoá (đã ghi chú trong review — data §Low).

---

## 5. Checklist khi có sự cố (incident)

1. Xác định phạm vi: mất DB? mất MinIO? hỏng 1 bảng? corruption?
2. Dừng ghi (`stop lims-api`) để không làm hỏng thêm.
3. Chọn nguồn khôi phục gần nhất đã **kiểm chứng**.
4. Restore theo §3, xác minh `alembic_version` + đếm bản ghi các bảng lõi
   (users, samples, chemical_transactions, audit_logs).
5. Bật lại app, kiểm `/health/ready` = ok (db/redis/minio) + `/metrics` không có 5xx tăng đột biến.
6. Ghi lại post-mortem: nguyên nhân, RPO/RTO thực tế đạt được, hành động phòng ngừa.

## 6. Việc cần tự động hoá (chưa làm — theo dõi)
- [ ] Cron backup pg_dump + mc mirror hằng ngày, đẩy off-site mã hoá.
- [ ] Job kiểm chứng restore hàng tháng (restore vào DB tạm + smoke test).
- [ ] Alert khi backup thất bại / quá hạn (không có bản mới > 24h).
- [ ] Cân nhắc PITR (WAL archiving) cho audit_logs nếu RPO 24h chưa đủ.
