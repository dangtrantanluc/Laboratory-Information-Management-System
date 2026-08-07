# DATABASE AUDIT — LIMS Backend

> PostgreSQL 15 · **68 bảng** · **32 migration Alembic** · **~250 index tường minh**
> ORM: SQLAlchemy 2.0.36 **đồng bộ** (psycopg2). Mã phát hiện: `D-xx`.

---

## 1. Đánh giá schema

### 1.1 Những thứ làm ĐÚNG (xác nhận bằng đọc migration)

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| **Primary key** | ✅ 68/68 bảng, UUID `gen_random_uuid()` server-side | mọi model |
| **Foreign key** | ✅ Có, kèm `ondelete` tường minh (`RESTRICT`/`CASCADE`/`SET NULL`) | `sample.py:35` (`RESTRICT`), `quotation.py:...` (`CASCADE` cho items), `attachment.py:49` (`RESTRICT` cho uploaded_by) |
| **UNIQUE constraint** | ✅ Có cho mọi mã nghiệp vụ: `uq_sample_code`, `uq_req_code`, `uq_doc_code`, `uq_equip_code`, `uq_nc_code`, `uq_risk_code`, `uq_improvement_code`, `uq_intake_code`, `uq_form_tpl_code`, `uq_quotation_code`, `uq_users_email`, `uq_rt_token_hash`, `uq_auth_tokens_hash` | migration + model |
| **CHECK constraint** | ✅ Dùng nhiều cho enum trạng thái, dấu số lượng, whitelist `owner_type` | `attachment.py:58-68`, `quotation.py:72-77` |
| **NOT NULL** | ✅ Áp đúng chỗ | |
| **Index** | ✅ **250 index** tạo ở migration `m22` + các migration sau. Có composite `(department_id, status)` cho bảng nghiệp vụ chính và `(owner_type, owner_id)` cho `attachments` | `alembic/versions/1718870400021_m22_schema_indexes.py` |
| **Index cho FK** | ✅ Đã bổ sung (`m22` + `m31_fk_indexes`) — Postgres không tự tạo | |
| **Timestamps** | ✅ `created_at`/`updated_at` `TIMESTAMP(timezone=True)` với `server_default now()` | mọi model nghiệp vụ |
| **Audit fields** | ✅ `created_by`/`updated_by` phổ biến | |
| **Bất biến bản ghi** | ✅ **Trigger Postgres**: `audit_logs` chặn UPDATE+DELETE (`m7_platform.py:251-265`); `calibration_records` chặn UPDATE+DELETE (`m5:124-150`); `capa` chặn UPDATE khi đã đóng + chặn DELETE (`m8:144-175`) | Đây là điểm mạnh nổi bật cho ISO/IEC 17025 §8.4 |
| **Kiểu số tiền** | ✅ `NUMERIC` + Decimal xuyên suốt, không dùng float | `hr_common.py`, `chemical_txn_service.py` |
| **Chống trùng thông báo cron** | ✅ 5 bảng `*_notification_dedup` với UNIQUE (đối tượng × mốc × ngày) + xử lý `IntegrityError` | `nc_cron_service.py:81`, `risk_cron_service.py:73`, `hr_cron_service.py:90` |
| **Migration** | ✅ Tuyến tính (32 revision, không nhánh), có `downgrade()`, chạy qua advisory lock, có dry-run trong CI | `entrypoint.sh:39-55`, `.github/workflows/backend-ci.yml` |

Đây là schema **trên mức trung bình đáng kể**. Phần lớn hệ thống cùng quy mô không có
trigger bất biến, không có 250 index có chủ đích, không có dedup key cho cron.

---

## 2. Phát hiện

### D-01 · 🟡 MEDIUM — Biên transaction do service tự quyết, 166 `db.commit()` rải rác

**Vị trí:** toàn bộ `app/services/*` (con số 166 do `app/tests/conftest.py:15` ghi nhận).

Mỗi service tự gọi `db.commit()` ở cuối hàm. Router chỉ có `Depends(get_db)` mở session và
đóng ở `finally` (`app/db/database.py:34-40`) — **không có `commit`/`rollback` ở tầng điều
phối**.

Hệ quả cụ thể:

1. **Không ghép được nhiều thao tác vào một transaction.** Muốn "tạo phiếu + tạo báo giá"
   nguyên tử là phải viết hàm service thứ ba, không gộp được từ hai hàm sẵn có.
2. **Commit lồng nhau.** `sample_flow_service.add_dispatches_batch` gọi nhiều helper, mỗi
   helper commit → mất tính nguyên tử của lô. Cần kiểm từng đường; ở đây chưa phát hiện
   trường hợp gây mất dữ liệu, nhưng bất biến không được bảo đảm bằng cấu trúc.
3. **Test phải dùng savepoint.** `conftest.py` phải bind session với
   `join_transaction_mode="create_savepoint"` để dọn được dữ liệu sau khi app đã commit.
4. **Rollback một phần không kiểm soát.** Chỉ có **một** chỗ dùng `begin_nested()` đúng
   cách (`chemical_txn_service._reorder_check` — bọc phần notify best-effort trong SAVEPOINT
   để không "poison" transaction chính). Các chỗ best-effort khác không có bảo vệ tương tự.

**Khắc phục (dài hạn):** chuyển `get_db` thành context quản lý transaction:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()          # commit một lần, ở biên request
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
```
và gỡ dần `db.commit()` khỏi service. Đây là việc lớn (166 điểm chạm) — nên làm theo module,
có test bao phủ trước.

### D-02 · 🟡 MEDIUM — N+1 query trong ~20 endpoint danh sách **[ĐO ĐƯỢC]**

**Vị trí:** 170 lời gọi `db.get(User, ...)` / `db.get(Department, ...)` per-row trong 23
service module.

Mẫu lặp lại:
```python
# app/services/hr_common.py:229-235
def user_name(db, user_id):
    u = db.get(User, user_id)          # 1 query mỗi lần gọi (trừ khi trúng identity map)
    return u.full_name if u else None
```
được gọi từ serializer từng dòng:
```python
# app/services/activity_service.py:59
return [_contract_dict(db, c) for c in rows], total
```

Với `limit=100` và 100 người tạo khác nhau → **101 query** cho một trang.

Các endpoint bị ảnh hưởng (danh sách rút gọn): `/research-contracts`, `/staff-activities`,
`/training-certificates`, `/activity-reports`, `/audit-logs`, `/customer-info-requests`,
`/equipments`, `/documents`, `/calibrations`, `/sample-flow/intakes`, `/sample-flow/dispatches`,
`/departments`, `/reports/system-access`.

**Đã sửa ở 2 chỗ** (`list_samples` — commit `2c6c552` gom lô, giảm 40%; `/forms/templates` —
commit `7e5883b`, giảm 70%). Mẫu sửa đã có sẵn, chỉ chưa áp cho phần còn lại.

**Giảm nhẹ:** SQLAlchemy identity map cache theo session → nếu 100 dòng cùng một `created_by`
thì chỉ 1 query. Trong thực tế phòng lab ~40 người, hệ số khuếch đại thực tế thấp hơn lý
thuyết nhiều. Vì vậy xếp MEDIUM chứ không HIGH.

**Khắc phục:** nạp trước theo lô:
```python
user_ids = {r.created_by for r in rows} | {r.owner_id for r in rows}
users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
```

### D-03 · 🟡 MEDIUM — Sinh mã bằng `COUNT()+1`: 2 chỗ không có retry → HTTP 500 khi đồng thời

**Cơ chế chung:** mọi mã nghiệp vụ được sinh bằng `COUNT(*) WHERE code LIKE 'PREFIX-YYYY-%'`
rồi `+1`. Không có sequence, không có lock. Hai request đồng thời đọc cùng `count` → cùng mã.

| Nơi sinh mã | UNIQUE ở DB | Retry `IntegrityError`? | Kết quả khi đồng thời |
|---|---|---|---|
| `risk_common.next_code` → `risk_service.create_risk` | ✅ `uq_risk_code` | ✅ 5 lần (`risk_service.py:113-135`) | OK |
| `risk_common.next_code` → `create_improvement` | ✅ | ✅ | OK |
| `nc_common.next_nc_code` → `nc_service` | ✅ `uq_nc_code` | ✅ (`nc_service.py:135`) | OK |
| `document_common.next_document_code` | ✅ `uq_doc_code` | ✅ (`document_service.py:200`) | OK |
| `equipment_common.next_equipment_code` | ✅ `uq_equip_code` | ✅ (`equipment_service.py:322`) | OK |
| `sample_common._next_code` (request/sample) | ✅ | ✅ (`test_request_service.py:207`) | OK |
| **`sample_flow_service._next_intake_code`** (`:49-55`) → `create_intake` (`:201-225`) | ✅ `uq_intake_code` | ❌ **KHÔNG** | **500 Internal Server Error** |
| **`quotation_service._next_code`** (`:53-61`) → `create_quotation` (`:186-...`) | ✅ `uq_quotation_code` | ❌ **KHÔNG** | **500 Internal Server Error** |

**Kịch bản thật:** hai nhân viên Phòng nhận mẫu bấm "Tạo phiếu" trong cùng một giây — một
người nhận 500, phiếu không được tạo, không có thông báo hữu ích. Với ~40 người dùng, xác
suất thấp nhưng khác 0, và **đúng vào giờ cao điểm nhận mẫu buổi sáng**.

**Vấn đề thứ hai của `COUNT()+1`:** nếu một bản ghi bị xoá cứng, `COUNT` giảm → mã tiếp theo
**trùng mã đã tồn tại** → `IntegrityError` **vĩnh viễn** (retry cũng ra cùng số). Với các
bảng dùng retry, vòng lặp 5 lần sẽ thất bại hẳn. Hiện `risks`/`nonconformities` không có
endpoint DELETE nên chưa xảy ra; `sample_intakes` và `quotations` **có** DELETE
(`quotations.py:136`) → đây là bom hẹn giờ.

`quotation_service._next_code` dùng biến thể khác — `ORDER BY code DESC LIMIT 1` rồi `+1`.
Miễn nhiễm với xoá, nhưng vẫn race, **và** sai khi vượt 9999 (so sánh chuỗi:
`'BG-2026-10000' < 'BG-2026-9999'`).

**Khắc phục:**
1. Ngắn hạn: bọc `create_intake` và `create_quotation` trong vòng retry giống 6 chỗ kia.
2. Đúng: dùng `CREATE SEQUENCE` per (prefix, năm), hoặc bảng `code_counters` với
   `UPDATE ... RETURNING` (nguyên tử, không phụ thuộc số bản ghi hiện có).

### D-04 · 🟡 MEDIUM — Tổng hợp báo cáo trong bộ nhớ, không giới hạn số dòng

**Vị trí:** `app/services/unified_report_service.py:81-86`

```python
time_rows = db.execute(select(col).where(*conditions)).scalars().all()   # KHÔNG có LIMIT
buckets = {}
for at in time_rows:
    key = rc.period_key(at, group_by)
    buckets[key] = buckets.get(key, 0) + 1
```

Kéo **toàn bộ** cột thời gian của mọi mẫu khớp bộ lọc về Python để đếm theo kỳ — việc mà
`GROUP BY date_trunc(...)` làm trong DB với chi phí gần bằng không.

Ở 1.000 mẫu: không đáng kể. Ở 100.000 mẫu (mục tiêu tăng trưởng trong đề bài): 100.000
`datetime` object trong RAM của một worker có `mem_limit: 1g` chia cho 4 process.

**Khuếch đại:** kết quả có cache (`rc.cache_get/cache_set`), nhưng **khoá cache gồm các
tham số do client điều khiển** (`from`, `to`, `group_by`, `status`, `time_field`, `breakdown`
— `unified_report_service.py:58-64`). Người dùng đã đăng nhập chỉ cần đổi `from` một ngày
mỗi lần là **luôn miss cache** → mỗi request là một lần quét toàn bảng. Endpoint này
(`GET /reports/samples`) **không có rate limit**.

**Khắc phục:** thay bằng aggregate trong SQL:
```sql
SELECT date_trunc('month', received_at) AS period, count(*)
FROM samples WHERE ... GROUP BY 1 ORDER BY 1
```

### D-05 · 🟡 MEDIUM — `attachments.owner_id` không có khoá ngoại (polymorphic)

**Vị trí:** `app/models/attachment.py:42-43` — *"owner_id KHÔNG FK cứng"* (ghi ở docstring dòng 1).

Đánh đổi có chủ đích của mẫu polymorphic, nhưng hệ quả phải được ghi nhận:

1. **Không có toàn vẹn tham chiếu.** Xoá một `document_version` không xoá/không chặn
   attachment của nó → mồ côi im lặng. Không có `ON DELETE CASCADE`.
2. **Kết hợp với S-02** (không kiểm owner tồn tại khi upload): có thể tạo attachment trỏ
   tới `owner_id` **không tồn tại** — dữ liệu rác không phát hiện được bằng ràng buộc DB.
3. **Không kiểm chéo `owner_type` ↔ bảng thật.** CHECK constraint chỉ giới hạn tập giá trị
   `owner_type`, không xác minh `owner_id` thuộc đúng bảng đó.

**Khắc phục:** ít nhất thêm job đối soát định kỳ (báo cáo attachment mồ côi), và kiểm owner
tồn tại ở tầng ứng dụng khi tạo. Nếu muốn chặt hơn: bảng nối riêng cho mỗi owner_type
(đắt), hoặc trigger kiểm tra.

### D-06 · 🟡 MEDIUM — Phân trang trong bộ nhớ

**Vị trí:** `app/services/document_version_service.py:53-70`

```python
rows = db.execute(select(DocumentVersion).where(...)).scalars().all()   # TẤT CẢ version
visible = [v for v in rows if dc.can_view_unpublished_version(user, doc, v)]
page_rows = visible[start:start+limit]
```

Lý do chính đáng: khả năng xem phụ thuộc quyền theo từng dòng, không biểu diễn được trong
SQL đơn giản. Nhưng hệ quả là `total` và phân trang tính trên tập đã tải hết về app.

Cùng mẫu: `hr_service.list_competences` (`:509-531`) không phân trang gì cả; `chemicals`
FEFO; `department_service._serialize` dựng cây phòng ban trong Python.

Với dữ liệu hiện tại (hàng chục–hàng trăm dòng) đây không phải vấn đề. Ghi nhận để không
sao chép sang module có bảng lớn.

### D-07 · 🔵 LOW — `purge_orphan_attachments` lặp lại vô hạn cùng một tập dòng

**Vị trí:** `app/services/cleanup_service.py:79-107`

```python
rows = db.execute(text("SELECT id, file_key FROM attachments "
                       "WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff LIMIT :lim"), ...)
for att_id, file_key in rows:
    storage_service.remove_object(file_key)     # xoá object MinIO
# ← KHÔNG cập nhật gì trên hàng attachments
```

Sau khi xoá object, **hàng DB không được đánh dấu**. Lần chạy hôm sau chọn lại đúng tập đó
và gọi `delete_object` lần nữa — S3/MinIO trả thành công cho key không tồn tại, nên không
có lỗi, chỉ có công vô ích và **số liệu `objects_removed` sai vĩnh viễn** (báo cáo đã xoá N
object mỗi ngày trong khi thực tế đã xoá từ lâu).

Đồng thời, hàng `attachments` mồ côi (đã mất file) tồn tại mãi trong DB.

**Khắc phục:** thêm cột `purged_at` (hoặc `file_key = NULL`) và lọc `AND purged_at IS NULL`.

### D-08 · 🔵 LOW — Lệch giữa model ORM và migration

**Ví dụ xác nhận:** `quotations.code`
- Migration `m29` dòng 63: `sa.UniqueConstraint("code", name="uq_quotation_code")` ✅
- Model `app/models/quotation.py:43` + `__table_args__` (dòng 72-77): **chỉ có CheckConstraint
  status**, không khai UNIQUE.

Không gây lỗi ở production (DB là nguồn sự thật, migration đã tạo constraint), nhưng:
- Ai đọc model sẽ kết luận sai là không có ràng buộc duy nhất.
- Nếu môi trường nào đó dựng schema bằng `Base.metadata.create_all()`, constraint biến mất.
  `conftest.py:38-43` đã **cố ý** không dùng `create_all` vì lý do này — nghĩa là vấn đề đã
  được biết đến ở phạm vi test nhưng chưa được sửa ở model.

**Khắc phục:** thêm test kiến trúc so sánh `Base.metadata` với schema thật sau `alembic upgrade head`.

### D-09 · 🟡 MEDIUM — Không có `statement_timeout`

Postgres chạy với `log_min_duration_statement=500ms` (ghi log truy vấn chậm ✅) nhưng
**không có `statement_timeout`**. Một truy vấn báo cáo trên bảng lớn chạy đến khi xong,
giữ cả connection lẫn worker slot.

Cấu hình hiện tại: `max_connections=200`, ứng dụng dùng 4 × (12+28) = 160. Chỉ cần vài chục
truy vấn chậm đồng thời là cạn pool → `db_pool_timeout=5s` bắt đầu ném lỗi cho mọi request
khác (fail-fast, đúng thiết kế) — nhưng nguyên nhân gốc không bị chặn.

**Khắc phục:**
```yaml
command: [..., -c, statement_timeout=30s, -c, idle_in_transaction_session_timeout=60s]
```
Đặt riêng giá trị cao hơn cho vai trò migrate.

### D-10 · 🔵 LOW — Soft delete chỉ áp cho 6/68 bảng, không nhất quán

Bảng có `deleted_at`: `attachments`, `equipments`, `samples`, `documents`, `customers`,
`test_requests`.

Bảng **không** có: `quotations` (có endpoint DELETE — xoá cứng), `research_projects`,
`publications`, `student_mentorships`, `teaching_courses`, `research_contracts`,
`staff_activities`, `training_certificates`, `activity_reports`, `competences`,
`lab_access_cards` (tất cả đều có endpoint DELETE).

Với hệ thống chịu ISO/IEC 17025, xoá cứng bản ghi nghiệp vụ làm mất vết. Hiện `audit_logs`
vẫn ghi hành động DELETE (append-only, không xoá được) nên **vết hành động còn**, nhưng
**nội dung bản ghi đã mất**. Cần quyết định có chủ đích: bảng nào được xoá cứng, bảng nào
không, và ghi lại lý do.

Ngoài ra: xoá cứng `quotations` phá cơ chế sinh mã (xem D-03).

### D-11 · 🟠 HIGH — Backup đã viết sẵn nhưng CHƯA ĐƯỢC BẬT trên host production

> **ĐÍNH CHÍNH 2026-08-07.** Bản đầu viết *"trong repo không có gì thực thi: không service
> backup, không cron, không script"* — **sai**, lần quét đầu bị `head -300` cắt mất 3 thư
> mục con của `ops/`. Mức độ (HIGH) và kết luận (RPO/RTO = ∞) **không đổi**, nhưng nguyên
> nhân và chi phí khắc phục đổi hẳn: từ *"phải xây"* thành *"phải bật"* (~30 phút).

**Đã có sẵn trong repo, và viết tốt:**

| Tệp | Nội dung |
|---|---|
| `ops/backup/lims-backup.sh` | `set -euo pipefail`; `pg_dump -Fc`; **kiểm toàn vẹn bằng `pg_restore --list`**; kiểm kích thước > 1KB cho cả dump lẫn tar; **hỏi `docker compose config` để lấy đúng tên volume** — tránh bẫy tar 0 byte từ volume rỗng, cạm bẫy được ghi chú ngay trong script; xoay bản cũ `KEEP_DAYS=14`; rsync off-site kèm cảnh báo khi chưa đặt đích |
| `ops/cron/lims-backup.cron` | cron 02:00 hằng ngày |
| `DEPLOY_LINUX.md:329-341` | hướng dẫn cài đặt |
| `DEPLOY_LINUX.md` §12 | checklist đã có `[ ] Cron backup 02:00 đã bật` + `[ ] ĐÃ diễn tập restore ít nhất một lần` |
| `ops/RUNBOOK.md:183` | việc hằng ngày: kiểm `/var/log/lims-backup.log` có dòng `HOÀN TẤT` |

**Nhưng chưa được cài — xác minh trên chính host production:**
```
$ docker inspect lims-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
/home/tanluc/workspace/lims        ← host này CHÍNH LÀ nơi chạy prod + cloudflare

$ ls /etc/cron.d/lims-backup /usr/local/bin/lims-backup /var/backups/lims /var/log/lims-backup.log
No such file or directory   (cả 4)
$ crontab -l  →  no crontab for tanluc
```

`lims-backend/docs/DISASTER_RECOVERY.md` nêu đúng nguyên tắc — *"backup KHÔNG kiểm chứng =
không có backup"* — ở đây thậm chí chưa có bản backup nào để mà kiểm chứng.

**Bốn chỗ phải sửa trước khi cài** (chi tiết ở REMEDIATION_PLAN P0-5): `LIMS_DIR` mặc định
`/opt/lims` ≠ thư mục thật; `LIMS_BACKUP_REMOTE` còn là placeholder `user@backup-host`; tên
tệp lệch giữa `DEPLOY_LINUX.md` (`lims-backup.sh`) và file cron (`lims-backup`); script gọi
`docker compose` **không có `-f`** nên nạp file compose **dev** (hiện chạy được do trùng tên
project/service/volume — đã đối chiếu `docker inspect lims-minio` → `lims_lims_miniodata`).
**Còn thiếu:** dump rsync off-site **chưa mã hoá**, trong khi nó chứa toàn bộ PII, lương và
nhật ký kiểm toán.

Volume `lims_pgdata` / `lims_miniodata` là local Docker volume trên một host duy nhất.

**Hỏng ổ đĩa = mất toàn bộ dữ liệu phòng thử nghiệm và toàn bộ nhật ký kiểm toán.**

- **RPO thực tế hiện tại: ∞** (không có bản sao nào)
- **RTO thực tế hiện tại: ∞** (không khôi phục được)
- **RPO mục tiêu đề xuất:** ≤ 24h cho dữ liệu nghiệp vụ; **≤ 15 phút** cho `audit_logs`
  (WAL archiving) vì ISO/IEC 17025 không cho phép mất vết
- **RTO mục tiêu đề xuất:** ≤ 4h (thực tế cho một host, dump logic)

### D-12 · 🔵 LOW — Read-modify-write không khoá ở một số đường PATCH

Phần lớn thao tác đổi trạng thái dùng `with_for_update()` đúng cách (13 vị trí: refresh
token, lô hoá chất, mẫu, thiết bị, tài liệu, NC, rủi ro, đăng ký PTN).

Nhưng các `PATCH` "sửa thông tin thường" thì không:
```python
# app/services/sample_flow_service.py:228-245  update_intake
it = db.get(SampleIntake, intake_id)          # đọc, không khoá
for k, v in changes.items(): setattr(it, k, v)
db.commit()                                    # ghi
```
Hai người sửa cùng phiếu → **lost update** (người ghi sau đè toàn bộ, kể cả field mình
không sửa — vì `changes` là `exclude_unset` nên thực tế chỉ đè field mình gửi; rủi ro thấp
hơn nhưng vẫn có với field cùng tên).

Đáng chú ý: `update_intake` cho phép đổi cả `status` qua PATCH thường
(`schemas/sample_flow.py:38`) **song song với** endpoint chuyên dụng
`POST /intakes/{id}/status` — hai đường đổi trạng thái, chỉ một đường có kiểm chuyển trạng
thái. Xem BUSINESS LOGIC trong PRODUCTION_READINESS.

**Khắc phục:** optimistic locking (cột `version`, kiểm `WHERE version = ?`) cho các bảng
nhiều người cùng sửa; hoặc `with_for_update()` như các module khác.

---

## 3. Kiểm tra race condition / double-booking

Hệ thống **không có** đặt phòng/mượn thiết bị theo lịch, nên không có "double booking" theo
nghĩa đen. Các tài nguyên có tính cạnh tranh tương đương:

| Tài nguyên | Mẫu "check → act" | Có bảo vệ? |
|---|---|---|
| **Tồn kho hoá chất** (xuất quá tồn) | Đọc `qty_base` → kiểm → trừ | ✅ `SELECT ... FOR UPDATE` trên lô (`chemical_txn_service.py:127`) + `balance_after` snapshot + CHECK không âm |
| **Refresh token** (dùng lại song song) | Đọc → kiểm revoked → xoay | ✅ `with_for_update()` (`auth_service.py:244`) — 2 refresh song song bị tuần tự hoá, cái sau thấy `revoked` → reuse detection |
| **Duyệt bản tài liệu** | Đọc version → kiểm trạng thái → duyệt | ✅ `get_version_or_404(lock=True)` (`document_version_service.py:405`) |
| **Đóng CAPA / rủi ro** | Đọc → kiểm → đóng | ✅ `lock=True` (`nc_common.py:105`, `risk_common.py:111`) |
| **Đăng ký PTN** | Đọc → kiểm → duyệt | ✅ `with_for_update()` (`research/registration_service.py:152`) |
| **Thẻ vào PTN** | Cấp thẻ | ⚠️ Chưa kiểm trùng thẻ đang hiệu lực bằng ràng buộc DB |
| **Sinh mã nghiệp vụ** | `COUNT()` → `+1` → INSERT | ⚠️ 6/8 có retry; 2 chỗ không (D-03) |
| **Duyệt tài khoản đăng ký** | | ✅ Có test `test_registration_race.py` |
| **Cron chạy trùng** | | ✅ 3 lớp: env flag → leader-lock → per-job lock. ⚠️ fail-open khi Redis chết (A-07) |

**Kết luận:** các đường có tiền/tồn kho/trạng thái quan trọng đều đã khoá đúng. Đây là phần
được làm cẩn thận.

---

## 4. Ước lượng hiệu năng theo quy mô

| Quy mô | Đánh giá |
|---|---|
| **100 người dùng, 10.000 bản ghi** | ✅ Không vấn đề. Index đầy đủ, pool 160 connection dư |
| **1.000 người dùng đồng thời** | ❌ Vượt thiết kế. 4 worker × 40 = 160 request đồng thời; sync SQLAlchemy + psycopg2 → mỗi request giữ 1 thread. Cần scale ngang (nhưng semaphore per-process và scheduler leader-lock đã có sẵn cho việc này) |
| **100.000 bản ghi mẫu** | ⚠️ Điểm nghẽn theo thứ tự: (1) D-04 báo cáo tổng hợp trong RAM, (2) D-02 N+1 ở list, (3) `access_stats` — bảng lớn nhất, đã có cleanup 90 ngày ✅, (4) `audit_logs` — **không có cleanup** (append-only, đúng cho 17025, nhưng cần chiến lược partition theo năm) |
| **1.000.000 dòng `audit_logs`** | ⚠️ Chưa có partition. `/audit-logs` có phân trang + index `user_id`/`created_at` nên OK; nhưng `system_access_service` group-by trên toàn bảng sẽ chậm dần |

---

## 5. Tổng hợp

| ID | Mức | Vấn đề | Vị trí | Ưu tiên |
|---|---|---|---|---|
| D-11 | 🟠 HIGH | Script backup viết sẵn & tốt nhưng **chưa cài** trên host → RPO/RTO thực tế = ∞ | `ops/backup/lims-backup.sh` (chưa có ở `/etc/cron.d/`) | **P0** |
| D-01 | 🟡 MEDIUM | 166 `db.commit()` trong service; biên transaction không kiểm soát được | `app/services/*` | P2 |
| D-02 | 🟡 MEDIUM | N+1 ở ~20 endpoint list (170 `db.get` per-row) | 23 service module | P1 |
| D-03 | 🟡 MEDIUM | `COUNT()+1` không retry ở `create_intake`, `create_quotation` → 500; và trùng mã sau xoá cứng | `sample_flow_service.py:49`, `quotation_service.py:53` | P1 |
| D-04 | 🟡 MEDIUM | Tổng hợp báo cáo trong RAM, không LIMIT, cache bypass được | `unified_report_service.py:81` | P1 |
| D-05 | 🟡 MEDIUM | `attachments.owner_id` không FK → mồ côi, không toàn vẹn | `models/attachment.py:43` | P2 |
| D-06 | 🟡 MEDIUM | Phân trang trong bộ nhớ | `document_version_service.py:53-70` | P2 |
| D-09 | 🟡 MEDIUM | Không có `statement_timeout` | `docker-compose.prod.yml:27-44` | P1 |
| D-07 | 🔵 LOW | Cleanup lặp lại vô hạn cùng tập dòng | `cleanup_service.py:79-107` | P2 |
| D-08 | 🔵 LOW | Lệch model ↔ migration (`uq_quotation_code`) | `models/quotation.py:72` | P3 |
| D-10 | 🔵 LOW | Soft delete chỉ 6/68 bảng, không nhất quán | nhiều model | P2 |
| D-12 | 🔵 LOW | PATCH không khoá → lost update | `sample_flow_service.py:228` | P3 |
