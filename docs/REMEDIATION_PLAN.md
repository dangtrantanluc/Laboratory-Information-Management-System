# REMEDIATION PLAN — LIMS Backend

> Nguồn: `SECURITY_AUDIT.md` (S-xx), `API_AUDIT.md` (API-xx), `DATABASE_AUDIT.md` (D-xx),
> `ARCHITECTURE_AUDIT.md` (A-xx), `PRODUCTION_READINESS.md` (B-xx), `THREAT_MODEL.md` (T-xx).
>
> Ước lượng công là **người-ngày** cho một lập trình viên đã quen codebase.

---

## TRẠNG THÁI THỰC THI — cập nhật 2026-08-07

| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| **P0-1** secret/git | ✅ **XONG** | `.gitignore` → `.env.*` + `!*.example`; `git check-ignore` xác nhận `.env.prod.bak.20260729` đã bị chặn; `git status` sạch |
| **P0-2** uỷ quyền `/attachments` | ✅ **XONG** | `app/services/attachment_authz.py` (14 guard, deny-by-default); `attachment_service` gọi vào; FE `Forms.tsx` chuyển sang `replaceFormFile`; `uploadFormFile` đã gỡ. 11 test mới |
| **P0-3** quyền đọc `/quotations` | ✅ **XONG** | `require_roles("admin","leader","reception","office")` + rate limit + `export_slot()`; FE `canViewQuotations` khớp. 10 test mới |
| **P0-4** state machine phiếu | ✅ **XONG** | `status` gỡ khỏi `UpdateIntakeRequest`; `setattr` mù → `_UPDATABLE_INTAKE_FIELDS`. 5 test mới |
| **P0-5** backup | ⚠️ **CÒN LẠI CHO NGƯỜI VẬN HÀNH** | 4 lỗi trong script đã sửa (compose `-f`, tên tệp, `cd` fail-fast, metric Prometheus). **Việc cài cần `sudo` → chưa chạy.** Xem lệnh ở P0-5 |
| **P2-15** RUNBOOK/compose | 🔶 **MỘT PHẦN** | `scripts/test-backend.sh` đã có chốt an toàn + `test-backend-isolated.sh` mới. `ops/RUNBOOK.md` **chưa sửa** |

**Kiểm chứng:** `579 passed, 6 skipped, 0 failed` · coverage **49,3%** (cổng CI 45%) ·
`ruff check app` → All checks passed · `tsc --noEmit` → 0 lỗi.

### Phát sinh trong lúc thực thi — 2 việc mới

**1. `scripts/test-backend.sh` đã phá stack production (đã khôi phục).**
Script gọi `docker compose` với hồ sơ **dev** trong khi production chạy từ **cùng thư
mục** → cùng tên project `lims` → Docker **recreate** `lims-postgres` và `lims-redis`
theo định nghĩa dev. Hậu quả đo được: Redis **mất `--requirepass`** (jti denylist,
lockout, rate limit mở toang) và cả hai publish cổng ra host (5460/6460). Dữ liệu
không mất (volume giữ nguyên). Đã khôi phục bằng `up -d` với đủ 2 hồ sơ; xác minh
`/health/ready` → `db/redis/minio: true`, không cổng nào publish.
→ Đây là **bằng chứng thực nghiệm** cho S-09/T-06: cạm bẫy "chạy compose thiếu `-f`"
không phải giả thuyết. `ops/RUNBOOK.md` có 15 lệnh cùng dạng, gồm thủ tục rollback.

**2. 3/9 cron job FAILED trên production — ĐÃ ĐIỀU TRA VÀ VÁ XONG.**

Hai nguyên nhân độc lập, cả hai đều tái hiện được 100%:

**(a) `data-cleanup` — chưa từng chạy được lần nào.**
`cleanup_cron_service.run_cleanup()` khai **0 tham số** và tự mở session, trong khi
`scheduler._run_tracked` gọi `service_call(db)` cho mọi job. 8/9 service nhận `db` làm
tham số đầu; đây là hàm duy nhất lệch quy ước.
```
TypeError: run_cleanup() takes 0 positional arguments but 1 was given
```
Hệ quả: `auth_tokens` hết hạn, `access_stats` quá 90 ngày và object MinIO mồ côi **chưa
bao giờ được dọn**. Thiệt hại hiện tại **bằng không** — hệ thống mới chạy từ 26/07 nên
chưa dòng nào chạm ngưỡng 90 ngày; nó sẽ bắt đầu cắn từ khoảng **24/10/2026**.

**(b) `capa-due` + `risk-review-due` — `audit_service._sanitize()` nổ với khoá số.**
```
AttributeError: 'int' object has no attribute 'lower'
  audit_service.py:37   if key.lower() in _SENSITIVE_KEYS
```
Ba cron nhắc hạn truyền `by_milestone = {7: 0, 3: 0, 0: 0}` — **khoá số** — vào
`detail`. `_sanitize` đệ quy vào dict lồng rồi gọi `key.lower()`. Chính các hàm này đã
ép `str(k)` cho **giá trị trả về**, nhưng quên `detail` của audit.

Ba cron cùng dính, hậu quả khác nhau vì cách bắt lỗi khác nhau:

| Cron | Bắt exception? | Hậu quả thật |
|---|---|---|
| CRON-7 `capa-due` | ❌ | Job FAILED. `db.commit()` không tới → **notification của lô đó bị rollback, mất hẳn** |
| CRON-8 `risk-review-due` | ❌ | Như trên |
| CRON-5 `equipment-calibration-due` | ✅ `except Exception: db.rollback()` **không log gì** | Job báo **"ok"** nhưng dòng audit im lặng biến mất |

**Kiểm chứng trên DB production** — chỉ 2/5 loại audit CRON từng được ghi:
```
 CRON_CONTRACT_EXPIRY_RUN | 5 | 2026-08-03
 CRON_SALARY_RAISE_RUN    | 5 | 2026-08-03
 (CRON_CALIBRATION_REMINDER, CRON_CAPA_REMINDER, CRON_RISK_REVIEW_REMINDER: 0 dòng)
```
Với hệ chịu ISO/IEC 17025, đây là **mất vết kiểm toán của 3 chu trình nhắc hạn** kể từ
ngày triển khai — và `except` không log là lý do không ai biết.

**Đã sửa (4 phần):**
1. `audit_service._sanitize` ép khoá về `str` — sửa gốc: hàm ghi nhật ký là mối quan
   tâm cắt ngang, **không được phép làm đổ vỡ nghiệp vụ mà nó đang ghi lại**.
2. 3 cron ép `{str(k): v}` trong `detail` (khớp phép chuyển đã dùng ở giá trị trả về).
3. `cleanup_cron_service.run_cleanup(db)` nhận `db`, bỏ session tự mở.
4. Hai chỗ `except Exception: db.rollback()` **không log** → thêm `logger.exception`.
   Giữ lưới an toàn, nhưng không giấu nó nữa.

**Kiểm chứng bản vá** trên bản sao dữ liệu production thật (`pg_dump` → `pg_restore` →
chạy cả 9 cron): **9/9 OK**, và 3 loại audit trước đây mất hẳn nay đã ghi được.

**Test mới `app/tests/test_cron_contract.py` (30 test)** khoá lại cả lớp lỗi: chữ ký của
9 job phải nhận `db` theo vị trí, mọi tham số còn lại phải có mặc định, `_sanitize` phải
chịu được khoá số, và **chạy thật cả 9 cron trên DB thật**. Bài cuối là bài duy nhất bắt
được cả hai lỗi — test cũ gọi từng service bằng đối số viết tay nên không bao giờ chạm tới.

**Còn lại cho P1-3:** cảnh báo khi `scheduler_job_last_success == 0`. Cơ chế ghi
run-history vốn hoạt động tốt — vấn đề là **không ai đọc** trong 5 ngày.

---

## P0 — PHẢI SỬA TRƯỚC KHI DEPLOY

> Tổng ước lượng: **2,5–3 ngày** (P0-1 … P0-5). Không mục nào bỏ qua được.
>
> *Đã hiệu chỉnh sau đợt kiểm chứng lại 2026-08-07: P0-5 giảm từ 1–1,5 ngày xuống ~1,5 giờ
> (script backup đã có sẵn, chỉ chưa cài); P0-2 tăng nhẹ vì phương án tắt "gỡ endpoint"
> không khả thi; P0-6 hạ xuống P2-15.*

### P0-1 · Chặn secret rò rỉ qua Git (S-04 / T-03) — **30 phút**

Ưu tiên số 1 vì rẻ nhất và hậu quả thảm hoạ nhất.

```gitignore
# .gitignore
.env
.env.*
!.env.example
!.env.prod.example
!.env.*.example
```

```bash
# Di chuyển các bản sao lưu ra ngoài cây làm việc
mkdir -p ~/lims-secrets && mv .env.prod.bak.* ~/lims-secrets/
chmod 600 ~/lims-secrets/*
```

Thêm pre-commit hook **cục bộ** (gitleaks trong CI chỉ phát hiện SAU khi đã push):
```bash
# .git/hooks/pre-commit  (và ghi vào CONTRIBUTING.md để mọi người cài)
#!/usr/bin/env bash
gitleaks protect --staged --redact || {
  echo "gitleaks phát hiện secret trong staged changes — commit bị chặn"; exit 1; }
```

Sửa `scripts/init-env-prod.sh` để **thay thế biến tại chỗ** thay vì sinh file `.bak` mới,
và dọn `VAPID_*` khai trùng trong `.env.prod` (S-19).

**Kiểm chứng:** `git check-ignore -v .env.prod.bak.test` phải trả về dòng `.gitignore`.

---

### P0-2 · Uỷ quyền cấp đối tượng cho `/attachments` (S-01, S-02 / T-01) — **1,5–2 ngày**

Đây là lỗ hổng nghiêm trọng nhất. Hai phương án:

**Phương án A — Bảng định tuyến quyền, deny-by-default (khuyến nghị)**

`app/services/attachment_authz.py` (mới):
```python
"""Định tuyến quyền đọc/ghi attachment về đúng module sở hữu.

MẶC ĐỊNH LÀ TỪ CHỐI. owner_type nào chưa khai luật thì không ai đọc/ghi được —
để module mới buộc phải khai báo quyền thay vì thừa hưởng lỗ hổng."""

def assert_can_read(db, user, att) -> None:
    guard = _READ_GUARDS.get(att.owner_type)
    if guard is None:
        raise forbidden(f"Chưa khai báo luật đọc cho {att.owner_type}")
    guard(db, user, att.owner_id)

def assert_can_write(db, user, owner_type, owner_id) -> None:
    guard = _WRITE_GUARDS.get(owner_type)
    if guard is None:
        raise forbidden(f"Chưa khai báo luật ghi cho {owner_type}")
    guard(db, user, owner_id)
```

Mỗi module sở hữu export một hàm `assert_*` — tái dùng đúng luật đã có, không viết lại:

| owner_type | Guard đọc | Guard ghi |
|---|---|---|
| `document_version` | `document_common.can_view_restricted` + `can_view_unpublished_version` | `deny_office_write` + `assert_write_scope` + kiểm version chưa `approved` |
| `form_template` | `require_permission("form","read")` | `require_permission("form","manage")` |
| `form_submission` | `form_file_service._check_submission_scope` | `+ _check_submission_writable` |
| `hr_profile` | `hr_service._assert_competence_read` | `hc.assert_can_manage_competence` |
| `sample`, `sample_result`, `test_request` | `sample_common` (phạm vi phòng + trạng thái công bố) | `sample_common` write scope |
| `chemical`, `chem_lot` | `chemical_common.assert_read_scope` | `assert_write_scope` |
| `equipment`, `calibration` | `equipment_common` | `equipment_common` |
| `publication`, `research_*`, `teaching_course`, `staff_activity`, `training_certificate` | `hr_common.assert_research_access` + scope | như đọc |
| `sample_intake`, `sample_dispatch` | `require_permission("intake","read")` | `require_permission("intake","manage")` |

**~~Phương án B — Gỡ endpoint generic~~ → KHÔNG KHẢ THI**

> **ĐÍNH CHÍNH 2026-08-07.** Bản đầu khuyến nghị "làm B trước (nửa ngày), A sau". Đã rà
> frontend: **gỡ endpoint generic sẽ làm hỏng 4 luồng tải lên và 3 luồng tải xuống đang
> chạy.**

```
POST /attachments — 4 nơi gọi:
  lims-frontend/src/pages/Forms.tsx:413                  → form_template
  lims-frontend/src/pages/Forms.tsx:496                  → form_submission
  lims-frontend/src/components/sampleFlow/IntakeCreateModal.tsx:91 → sample_intake
  lims-frontend/src/pages/SampleFlow.tsx:755             → sample_dispatch

GET /attachments/{id} — 3 nơi gọi:
  Forms.tsx:222, Forms.tsx:609, DocumentPendingReview.tsx:243  (qua openFormFile)
  + sampleFlow.ts:127 openFile
```

Và quan trọng hơn: **`sample_intake` / `sample_dispatch` KHÔNG có endpoint riêng nào cả** —
`grep -E "@router\.(post|get)" app/routers/sample_flow.py | grep -i file` trả về rỗng.
Đường generic là đường **duy nhất** để đính kèm phiếu nhận/chuyển mẫu. Gỡ nó đi là mất tính
năng, không phải vá lỗ hổng.

→ **Bắt buộc làm phương án A.** Không có lối tắt.

**Phát hiện kèm theo (sửa cùng lúc, 15 phút):** frontend đã có sẵn **cả hai** đường cho
biểu mẫu VILAS, và đang dùng nhầm đường ở luồng tạo mới:

| Nơi | Hàm | Endpoint | RBAC |
|---|---|---|---|
| `FormFileManager.tsx:75` | `replaceFormFile` | `POST /forms/{owner}/{id}/file` | ✅ `form:manage`/`form:submit` + phạm vi phòng + khoá sau duyệt |
| **`Forms.tsx:413`** (tạo biểu mẫu gốc) | `uploadFormFile` | `POST /attachments` | ❌ Không có gì |
| **`Forms.tsx:496`** (nộp minh chứng) | `uploadFormFile` | `POST /attachments` | ❌ Không có gì |

`src/api/forms.ts:159` ghi rõ lý do đường riêng tồn tại — *"vì chỉ ở đây mới có RBAC
form:manage / form:submit + ràng buộc phòng ban và trạng thái duyệt"* — nhưng luồng tạo mới
vẫn gọi đường generic. Đổi 2 lời gọi sang `replaceFormFile` là xong.

**Phạm vi bảng định tuyến nhỏ hơn tưởng.** Chỉ **10 `owner_type` thực sự được ghi** trong
toàn bộ backend (`grep -rhoE 'owner_type="[a-z_]+"'`): `form_template`, `form_submission`,
`sample`, `test_request`, `sample_result`, `publication`, `hr_profile`, `equipment`,
`chemical`, `calibration` — cộng `sample_intake`/`sample_dispatch` từ frontend. 10 giá trị
còn lại trong `VALID_OWNER_TYPES` chưa bao giờ được dùng → cho vào nhánh **deny mặc định**,
không cần viết guard.

**Kiểm chứng bắt buộc — viết test tích hợp trước khi đóng:**
```python
def test_staff_khac_phong_khong_tai_duoc_tai_lieu_restricted(client, seeded):
    att_id = seeded.restricted_doc_attachment_id
    as_role("staff", department=seeded.dept_b)
    assert client.get(f"/api/v1/attachments/{att_id}").status_code == 403

def test_khong_dinh_kem_duoc_vao_minh_chung_da_duyet(client, seeded):
    as_role("staff")
    r = client.post("/api/v1/attachments",
                    data={"owner_type": "form_submission", "owner_id": seeded.approved_submission_id},
                    files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code in (403, 422)
```

---

### P0-3 · Phân quyền đọc cho `/quotations` (S-03 / T-01) — **2 giờ**

```python
# app/routers/quotations.py
quotation_read = require_roles("admin", "leader", "reception", "office")   # chốt với nghiệp vụ

@router.get("/quotations")
def list_quotations(..., user: CurrentUser = Depends(quotation_read), ...):

@router.get("/quotations/{quotation_id}")
def get_quotation(..., user: CurrentUser = Depends(quotation_read), ...):

@router.get("/quotations/{quotation_id}/export.xlsx",
            dependencies=[Depends(rate_limit("report-export", limit=10, window_seconds=60))])
def export_quotation_xlsx(..., user: CurrentUser = Depends(quotation_read), ...):
    with export_slot():          # cùng lúc vá API-07/T-09
        ...
```

**Danh sách vai trò phải được chốt với nghiệp vụ, không đoán.** Nếu chưa chốt được: dùng
`require_permission("quotation", "read")` và thêm dòng vào bảng `roles_permissions` —
khi đó sửa quyền không cần deploy.

**Kiểm chứng:** test `staff` gọi `GET /quotations` → 403.

---

### P0-4 · Vá bypass state machine phiếu nhận mẫu (B-01) — **2 giờ**

```python
# app/schemas/sample_flow.py — bỏ 'status' khỏi UpdateIntakeRequest
class UpdateIntakeRequest(BaseModel):
    customer_id: ...
    # status: ĐÃ BỎ — đổi trạng thái phải qua POST /intakes/{id}/status
    #   (state machine INTAKE_NEXT + kiểm vai trò _privileged)
```

```python
# app/services/sample_flow_service.py:236 — thay setattr mù bằng danh sách tường minh
_UPDATABLE = ("customer_id", "customer_name", "contact", "description", "note",
              "dispatch_note", "address", "tax_code", "contact_person", "phone",
              "email", "due_date", "result_language", "return_method",
              "fee_note", "other_request")
for k in _UPDATABLE:
    if k in changes:
        setattr(it, k, changes[k])
```

Mẫu đúng đã có sẵn trong cùng dự án: `quotation_service.update_quotation:312-320`.

**Kiểm chứng:** `PATCH /intakes/{id} {"status":"completed"}` → 400 `VALIDATION_ERROR`
(`extra="forbid"` đã bật).

---

### P0-5 · **CÀI ĐẶT** backup (đã viết sẵn, chưa bật) + diễn tập restore (D-11 / T-04) — **30 phút + 1 giờ diễn tập**

> **ĐÍNH CHÍNH 2026-08-07 — quan trọng.** Bản đầu viết *"không có gì thực thi: không service
> backup trong compose, không cron/systemd, không script trong `scripts/`"* và ước lượng
> 1–1,5 ngày để **xây mới**. **Sai.** Lần quét đầu bị `head -300` cắt mất 3 thư mục con của
> `ops/`. Thực tế đã có sẵn và viết tốt:
>
> - `ops/backup/lims-backup.sh` — `set -euo pipefail`; kiểm tính toàn vẹn dump bằng
>   `pg_restore --list`; kiểm kích thước > 1KB cho cả dump lẫn archive; **hỏi
>   `docker compose config` để lấy đúng tên volume** (tránh bẫy backup 0 byte từ volume rỗng
>   — cạm bẫy này được ghi chú rõ trong script); xoay bản cũ theo `KEEP_DAYS`; rsync off-site
>   với cảnh báo khi chưa đặt đích.
> - `ops/cron/lims-backup.cron` — cron 02:00 hằng ngày.
> - `DEPLOY_LINUX.md:329-341` — hướng dẫn cài đặt.
> - Checklist bàn giao `DEPLOY_LINUX.md` đã có 2 dòng: `[ ] Cron backup 02:00 đã bật` và
>   `[ ] ĐÃ diễn tập restore ít nhất một lần`.
>
> **Điều KHÔNG đổi — và vẫn là P0:** nó **chưa được cài trên máy đang chạy production**.

**Bằng chứng (máy chủ đang chạy, 2026-08-07):**
```
$ docker inspect lims-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
/home/tanluc/workspace/lims          ← đây CHÍNH LÀ host production (prod + cloudflare)

$ ls /etc/cron.d/lims-backup /usr/local/bin/lims-backup /var/backups/lims /var/log/lims-backup.log
ls: cannot access ... : No such file or directory     (cả 4)
$ crontab -l
no crontab for tanluc
```
→ **Hiện tại không tồn tại bản backup nào.** RPO = ∞ vẫn đúng; chỉ có chi phí khắc phục là
đổi từ "xây mới 1,5 ngày" thành "cài đặt 30 phút".

**Việc cần làm — và 4 chỗ phải sửa trước khi cài:**

| # | Vấn đề | Sửa |
|---|---|---|
| 1 | `LIMS_DIR` mặc định `/opt/lims`, cron cũng hardcode `/opt/lims`. Thư mục thật là `/home/tanluc/workspace/lims` → `cd` thất bại → `set -e` → exit 1, **không có backup nào** | Đặt `LIMS_DIR=/home/tanluc/workspace/lims` trong cron (hoặc chuyển deploy về `/opt/lims` cho khớp tài liệu) |
| 2 | `LIMS_BACKUP_REMOTE=user@backup-host:/lims` là **placeholder** → rsync thất bại → exit 1 *sau khi* dump cục bộ đã xong (báo lỗi nhưng backup vẫn có) | Đặt đích thật, hoặc bỏ hẳn biến và chấp nhận cảnh báo cho tới khi có NAS/S3 |
| 3 | `DEPLOY_LINUX.md:329-330` chép thành `/usr/local/bin/lims-backup**.sh**`, còn `ops/cron/lims-backup.cron` gọi `/usr/local/bin/lims-backup` (không `.sh`) → `command not found` | Thống nhất một tên. Khuyến nghị: bỏ `.sh` theo file cron |
| 4 | Script gọi `docker compose` **không có `-f`** → nạp `docker-compose.yml` (file DEV), không phải `prod + cloudflare`. Hiện *tình cờ chạy được* (tên project = tên thư mục = `lims`, service `postgres` tồn tại ở cả hai file, volume `lims_miniodata` giải ra `lims_lims_miniodata` giống nhau — đã đối chiếu với `docker inspect lims-minio`). Nhưng nó phụ thuộc vào việc file dev không bao giờ lệch | Thêm `-f docker-compose.prod.yml -f docker-compose.cloudflare.yml` vào cả 2 lời gọi trong script |

**Cài đặt (sau khi sửa 4 mục trên):**
```bash
sudo cp ops/backup/lims-backup.sh /usr/local/bin/lims-backup
sudo chmod +x /usr/local/bin/lims-backup
sudo cp ops/cron/lims-backup.cron /etc/cron.d/lims-backup   # đã sửa LIMS_DIR + REMOTE
sudo LIMS_DIR=/home/tanluc/workspace/lims /usr/local/bin/lims-backup   # chạy tay lần đầu
ls -lh /var/backups/lims/                                    # phải thấy db-*.dump + files-*.tar.gz
```

**Bổ sung còn thiếu — mã hoá off-site:** script hiện rsync bản dump **chưa mã hoá**. Dump
chứa toàn bộ PII, lương và nhật ký kiểm toán. Thêm `age`/`gpg --symmetric` trước bước rsync.

**Diễn tập restore — BẮT BUỘC, có biên bản (1 giờ):**
```bash
docker run -d --name pg-restore-test -e POSTGRES_PASSWORD=x postgres:15-alpine
docker exec -i pg-restore-test psql -U postgres -c "CREATE DATABASE lims_restore_test;"
docker exec -i pg-restore-test pg_restore -U postgres -d lims_restore_test \
    < /var/backups/lims/db-<ngày>.dump
docker exec pg-restore-test psql -U postgres -d lims_restore_test \
    -c "SELECT version_num FROM alembic_version;" \
    -c "SELECT count(*) FROM audit_logs;" -c "SELECT count(*) FROM samples;"
```
Đối chiếu số dòng với production, **ghi RTO đo được vào `ops/RUNBOOK.md`**, rồi tick 2 dòng
checklist đã có sẵn trong `DEPLOY_LINUX.md`. Nguyên tắc do chính tài liệu DR của dự án nêu:
*"backup KHÔNG kiểm chứng = không có backup"*.

---

### ~~P0-6 · Khoá đường giả mạo IP~~ → **ĐÃ CHUYỂN XUỐNG P2-15**

> **ĐÍNH CHÍNH 2026-08-07.** Mục này ban đầu nằm ở P0 với khuyến nghị `set_real_ip_from`
> dải IP công khai của Cloudflare. Sau khi xác minh triển khai thực tế, **cả mức ưu tiên
> lẫn nội dung kỹ thuật đều sai**:
>
> **(a) Không phải P0.** `docker ps` xác nhận overlay `docker-compose.cloudflare.yml` đang
> chạy: `lims-web` chỉ có `80/tcp`, không ánh xạ ra host; mạng `lims_default` chỉ gồm 6
> container LIMS + `cloudflared`. Không ai gọi thẳng nginx được, và biên Cloudflare **ghi
> đè** `CF-Connecting-IP` nên client không giả mạo được. Cấu hình hiện tại **đúng và tin
> cậy được** với topology này.
>
> **(b) Khuyến nghị `set_real_ip_from 173.245.48.0/20` là SAI với kiến trúc tunnel.** Với
> tunnel, `$remote_addr` mà nginx thấy là IP container `cloudflared` (172.22.0.3), **không
> bao giờ** là IP biên Cloudflare. Dải đó sẽ không bao giờ khớp → module `real_ip` không
> kích hoạt → `X-Real-IP` rơi về IP container → **tái tạo đúng lỗi** mà
> `app/core/request_meta.py` được viết ra để sửa (docstring ghi nhận 545/1.442 dòng
> `audit_logs` từng ghi `172.21.0.6`). Áp dụng nó sẽ làm hỏng nhật ký IP chứ không cải thiện.
>
> Việc **thật sự cần làm** là sửa `ops/RUNBOOK.md` — xem **P2-15**.

---

## P1 — SỬA TRƯỚC KHI ĐƯA VÀO VẬN HÀNH THẬT

> Tổng ước lượng: **4,5–7 ngày** (giảm sau khi phát hiện `ops/monitoring/` đã có sẵn cấu
> hình Prometheus + 5 alert). Làm trong 2–3 tuần đầu sau go-live có kiểm soát.

| # | Việc | Nguồn | Công |
|---|---|---|---|
| **P1-1** | **Xử lý Redis-down có chủ đích.** Bọc `is_jti_denied` + `_check_lockout` trong `try/except`, quyết định 503 + `Retry-After` (fail-closed rõ ràng) hoặc fail-open + log SECURITY. **Ghi lý do vào code** — hiện fail-closed là do quên, không phải do chọn | S-05, T-02 | 0,5đ |
| **P1-2** | **Sửa health check qua nginx.** Thêm `location = /health` và `= /health/ready`; `/health/ready` trả **503** khi degraded và **không kèm `errors`** ra ngoài; sửa `DEPLOY_LINUX.md` + checklist thành kiểm tra nội dung | S-10, S-11, A-03 | 0,5đ |
| **P1-3** | **BẬT monitoring (cấu hình đã viết sẵn, chưa chạy).** `ops/monitoring/prometheus.yml` (scrape lims-api + node-exporter + postgres-exporter) và `ops/monitoring/alerts.yml` (5 alert: `ApiDown`, `HighErrorRate`, `SlowResponses`, `DiskAlmostFull`, `BackupMissing`) **đã tồn tại**. Thiếu: (a) **không có compose nào dựng Prometheus/Alertmanager/exporter** — `docker ps -a` không có container giám sát nào; (b) alert `BackupMissing` dựa trên metric `lims_backup_last_success_timestamp_seconds` mà **không thành phần nào phát ra** — `ops/backup/lims-backup.sh` không ghi textfile, node-exporter chưa bật textfile collector → alert quan trọng nhất sẽ *không bao giờ kêu*. Việc cần làm: viết `docker-compose.monitoring.yml` + thêm 2 dòng ghi metric vào cuối script backup | Observability 4/10 | **0,75đ** (giảm từ 1,5đ) |
| **P1-4** | **Rate limit + `export_slot()` cho 2 đường xuất nặng nhất**: `GET /samples/{id}/result-report.pdf`, `GET /quotations/{id}/export.xlsx` | API-07, T-09 | 0,5đ |
| **P1-5** | **`statement_timeout=30s` + `idle_in_transaction_session_timeout=60s`** trên Postgres (đặt cao hơn cho vai trò migrate). Cân nhắc middleware timeout trả 504 | D-09, API-09 | 0,5đ |
| **P1-6** | **Chuyển tổng hợp báo cáo sang SQL.** `unified_report_service.py:81` → `GROUP BY date_trunc(...)`. Bỏ vòng lặp đếm trong Python | D-04, T-09 | 0,5đ |
| **P1-7** | **Retry `IntegrityError` cho `create_intake` và `create_quotation`** (sao chép mẫu 5-lần đã dùng ở `risk_service.py:113-135`) | D-03 | 0,5đ |
| **P1-8** | **Kiểm magic bytes khi upload** + `add_header X-Content-Type-Options nosniff always;` cho `location /lims-attachments/` | S-06, T-10 | 1đ |
| **P1-9** | **Allowlist host cho Web Push endpoint**; chặn IP literal và dải private/link-local | S-07, T-07 | 0,5đ |
| **P1-10** | **Bộ đếm brute-force thứ hai theo email toàn cục** (30/giờ) với hành vi mềm: delay tăng dần / CAPTCHA / cảnh báo admin + mail cho chủ tài khoản. **Không khoá cứng** — sẽ tạo DoS nhắm mục tiêu | S-08, T-05 | 1đ |
| **P1-11** | **Test tích hợp uỷ quyền cấp đối tượng.** Đúng loại test lẽ ra bắt được S-01/S-02/S-03. Bao phủ: `/attachments` cross-department, tài liệu `restricted`, `/quotations` theo vai trò, minh chứng đã duyệt | Testing 5/10 | 1,5đ |
| **P1-12** | **Sửa `reset_password` của admin** — gửi link đặt lại qua mail (tái dùng `_issue_token` + `PURPOSE_PASSWORD_RESET`) thay vì sinh mật khẩu không ai biết | B-02 | 0,5đ |
| **P1-13** | **Gom lô N+1 ở 5 endpoint list nặng nhất** (`/documents`, `/equipments`, `/sample-flow/intakes`, `/audit-logs`, `/research-contracts`) theo mẫu đã dùng ở `list_samples` | D-02 | 1đ |
| **P1-14** | **Phân trang thật cho `document_version_service.list_versions`** và thêm phân trang cho `list_competences` | D-06, API-06 | 0,5đ |
| **P1-15** | **Scheduler fail-closed** khi Redis lỗi; tách container riêng chuyên chạy cron (`--workers 1`, `SCHEDULER_ENABLED=true`), API set `SCHEDULER_ENABLED=false` | A-07, T-11 | 0,5đ |

---

## P2 — SỬA SAU KHI DEPLOY (trong quý)

| # | Việc | Nguồn | Công |
|---|---|---|---|
| **P2-1** | **Đảo mọi kiểm quyền denylist thành allowlist.** `hr_service.get_profile:187`, `deps.py:71`, và rà toàn bộ `if user.role == "x"` | S-13, S-14 | 0,5đ |
| **P2-2** | **Tách vai trò DB.** `lims_migrate` (owner, chỉ service migrate) và `lims_app` (chỉ DML, `REVOKE TRIGGER`, không DDL) → trigger append-only không bị credential ứng dụng gỡ được | S-18, T-08 | 1đ |
| **P2-3** | **Hardening container.** `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, `read_only: true` + `tmpfs`, ghim `minio/minio:RELEASE.20xx`, multi-stage build cho backend | S-16 | 0,5đ |
| **P2-4** | **Chuẩn hoá cơ chế phân quyền** về `require_permission` ở router cho quyền chức năng; service chỉ kiểm phạm vi đối tượng. Thêm test kiểm tính đầy đủ của ma trận `roles_permissions` | API-03, API-04 | 2đ |
| **P2-5** | **`response_model` cho endpoint chạm dữ liệu nhạy cảm** (HR, quotation, customer, audit, document) — lưới chắn chống lộ field ở tầng nền tảng | API-05 | 2đ |
| **P2-6** | **Nâng chính sách mật khẩu**: ≥12 ký tự, chặn danh sách 10.000 mật khẩu phổ biến (offline), chặn mật khẩu chứa local-part của email; hạ `max_length` xuống 72 hoặc pre-hash SHA-256 trước bcrypt | S-12 | 0,5đ |
| **P2-7** | **Bắt buộc `Idempotency-Key`** cho POST tạo phiếu/báo giá/giao dịch kho; cập nhật frontend gửi header | API-08 | 1đ |
| **P2-8** | **Chính sách soft-delete nhất quán** — quyết định có chủ đích bảng nào xoá cứng, bảng nào không, ghi lý do. Ưu tiên `quotations` (đang xoá cứng + sinh mã theo `MAX`) | D-10, B-03 | 1đ |
| **P2-9** | **Sửa `purge_orphan_attachments`** — thêm cột `purged_at`, lọc `AND purged_at IS NULL` | D-07 | 0,25đ |
| **P2-10** | **Chính sách lưu trữ dữ liệu cá nhân** (nhân viên nghỉ việc, khách hàng cũ); partition `audit_logs` theo năm | Data privacy | 1,5đ |
| **P2-11** | **Mã hoá at-rest** — mã hoá đĩa ở host (LUKS) hoặc mã hoá volume; bắt buộc cho backup off-site | Data privacy | 0,5đ |
| **P2-12** | **MFA (TOTP) cho vai trò `admin`** | T-05 | 2đ |
| **P2-13** | **Job đối soát attachment mồ côi** (`owner_id` trỏ tới bản ghi không tồn tại) | D-05 | 0,5đ |
| **P2-14** | **Trần cho `page`** trong `normalize_pagination` (chặn khi `offset > total`) | API-06 | 0,25đ |
| **P2-15** | **Sửa `ops/RUNBOOK.md` dùng đủ 2 file compose** (chuyển từ P0-6). `grep -c "cloudflare.yml" ops/RUNBOOK.md` → **0**; 15 lệnh dùng `-f docker-compose.prod.yml` đơn lẻ, gồm thủ tục **rollback dòng 149** — chạy đúng lệnh đó sẽ dựng lại `lims-web` có cổng 3060 và **không tạo `cloudflared`** (hệ thống offline với người dùng thật), đồng thời mở đường giả mạo `CF-Connecting-IP`. Dùng alias đã có sẵn ở `DEPLOY_LINUX.md:360`. Kèm theo: gỡ `ports: "3060:80"` khỏi `docker-compose.prod.yml`, chuyển sang overlay `docker-compose.lan.yml` riêng | S-09, T-06 | 0,5đ |

---

## P3 — DÀI HẠN / NICE TO HAVE

| # | Việc | Nguồn | Ghi chú |
|---|---|---|---|
| **P3-1** | **Chuyển biên transaction về `get_db`** — commit một lần ở biên request, gỡ dần 166 `db.commit()` khỏi service | D-01, A-01 | Việc lớn (~2 tuần). Làm theo module, cần test bao phủ trước |
| **P3-2** | **Thay `COUNT()+1` bằng SEQUENCE** hoặc bảng `code_counters` với `UPDATE ... RETURNING` | D-03 | Loại bỏ hẳn cả race lẫn trùng-mã-sau-xoá |
| **P3-3** | **Rời `python-jose` → `pyjwt`, `passlib` → `argon2-cffi`** | S-15 | Cần kế hoạch di trú hash (verify cả 2, rehash khi đăng nhập) |
| **P3-4** | **Tách repository layer** (hoặc ít nhất tách serializer ra khỏi service) | A-01 | Giải quyết gốc của 20+ import cục bộ và trần khả năng test |
| **P3-5** | **Tách nginx thành reverse proxy riêng**, không gộp với container SPA | A-03 | Đổi cấu hình proxy không phải build lại frontend |
| **P3-6** | **Semaphore phân tán** (Redis) thay `threading.BoundedSemaphore` per-process | A-11 | Chỉ cần khi scale ngang |
| **P3-7** | **Retry/backoff/dead-letter cho cron**; cân nhắc queue thật (Celery/Arq) nếu số job tăng | A-08 | |
| **P3-8** | **Gửi bản sao `audit_logs` sang kho WORM** (S3 Object Lock) | T-08 | Yêu cầu dài hạn của ISO/IEC 17025 |
| **P3-9** | **Thống nhất nguồn IP người gọi** — `auth.py` dùng chung `request_meta.client_ip` | API-10 | Gỡ phụ thuộc ngầm vào `--proxy-headers` |
| **P3-10** | **Test kiến trúc so sánh `Base.metadata` với schema thật** sau `alembic upgrade head` | D-08 | Bắt lệch model↔migration tự động |
| **P3-11** | **Ngưỡng gác hiệu năng trong CI** (đã có `loadtest/` và `perf/`, chưa có gate) | Performance | |
| **P3-12** | **Streaming cho export lớn** thay vì buffer toàn bộ trong RAM; sửa `IdempotencyMiddleware` dừng đọc khi vượt ngưỡng | A-05 | |

---

## Lịch trình đề xuất

```
Tuần 0 (trước deploy)   ████████    P0-1 … P0-5      2,5–3 ngày  → điều kiện để go-live
Tuần 1–3 (sau go-live)  ████████    P1-1 … P1-15     4,5–7 ngày  → vận hành thật an toàn
Tháng 2–3               ██████      P2-1 … P2-15      ~13 ngày   → củng cố
Quý 2+                  ████        P3-1 … P3-12       dài hạn   → nợ kiến trúc
```

**Thứ tự trong P0 (theo tỉ lệ giá trị/công sức):**

| Thứ tự | Mục | Công | Vì sao ở vị trí này |
|---|---|---|---|
| 1 | **P0-1** secret/git | 30 phút | Rẻ nhất, hậu quả thảm hoạ nhất |
| 2 | **P0-5** cài backup | 30 phút | Trước đây tưởng 1,5 ngày; hoá ra chỉ là chạy 4 lệnh. Làm ngay để **có bản backup đầu tiên trước khi động vào code** |
| 3 | **P0-4** state machine phiếu | 2 giờ | Sửa 2 file, có mẫu đúng ngay trong dự án (`update_quotation`) |
| 4 | **P0-3** quyền đọc báo giá | 2 giờ | 3 dòng `Depends` + test |
| 5 | **P0-2** uỷ quyền `/attachments` | 1,5–2 ngày | Lớn nhất, không có lối tắt. Làm sau khi đã có backup |
| 6 | **P0-5b** diễn tập restore | 1 giờ | Làm cuối, sau khi đã có ≥1 bản backup thật |

> **P2-15 (sửa `ops/RUNBOOK.md`) đáng làm sớm dù không phải P0** — mất 30 phút, và lý do
> mạnh nhất không phải bảo mật: thủ tục rollback hiện tại sẽ **làm mất `cloudflared`** →
> hệ thống offline với người dùng thật, đúng vào lúc đang xử lý sự cố.

> **P2-15 (sửa `ops/RUNBOOK.md`) đáng làm sớm dù không phải P0** — mất 30 phút, và lý do
> mạnh nhất không phải bảo mật: thủ tục rollback hiện tại sẽ **làm mất `cloudflared`** →
> hệ thống offline với người dùng thật, đúng vào lúc đang xử lý sự cố.

---

## Định nghĩa "xong" cho P0

Chỉ được deploy khi **tất cả** các mục sau đúng:

- [ ] `git check-ignore -v .env.prod.bak.test` trả về dòng khớp trong `.gitignore`
- [ ] pre-commit hook gitleaks đã cài và được ghi trong `CONTRIBUTING.md`
- [ ] Test tự động: `staff` phòng B **không** tải được attachment của tài liệu `restricted` phòng A
- [ ] Test tự động: `staff` **không** đính kèm được tệp vào minh chứng đã duyệt
- [ ] Test tự động: `staff` gọi `GET /quotations` trả **403**
- [ ] Test tự động: `PATCH /intakes/{id} {"status":"completed"}` trả **400**
- [ ] `Forms.tsx:413` và `Forms.tsx:496` đã chuyển sang `replaceFormFile` (đường có RBAC)
- [ ] `ls /var/backups/lims/` cho thấy **ít nhất 1 cặp** `db-*.dump` + `files-*.tar.gz` > 1KB
- [ ] `cat /etc/cron.d/lims-backup` có `LIMS_DIR` trỏ đúng thư mục deploy thật
- [ ] `curl https://<domain>/health` trả JSON của backend (không phải HTML SPA) — hoặc
      checklist đã được sửa để không dựa vào nó
- [ ] Một bản backup đã được **restore thành công** vào DB tạm, với biên bản ghi RTO đo được
- [ ] Backup được đẩy off-site và đã mã hoá
- [x] ~~`docker-compose.prod.yml` không publish cổng nào~~ — **đã đạt**: overlay Cloudflare
      đang chạy, `docker ps` xác nhận `lims-web` chỉ có `80/tcp`, không ánh xạ ra host
- [x] ~~nginx chỉ tin `CF-Connecting-IP` từ dải IP Cloudflare~~ — **mục này đã bị gỡ**: sai
      với kiến trúc tunnel (xem đính chính P0-6). Thay bằng P2-15 (sửa `ops/RUNBOOK.md`),
      không phải điều kiện go-live
