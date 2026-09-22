/**
 * Nút "Xuất Excel" dùng chung cho 8 màn hình Nghiên cứu & Đào tạo.
 *
 * MỘT COMPONENT CHO CẢ TÁM, KHÔNG PHẢI TÁM BẢN SAO
 * Tám trang cần đúng một thứ: chọn khoảng thời gian rồi tải file. Chép logic đó vào
 * từng trang là tám chỗ phải sửa khi đổi định dạng ngày hay thông báo lỗi. Ở đây mỗi
 * trang chỉ khai `kind`.
 *
 * NÓI RÕ ĐANG LỌC THEO NGÀY NÀO
 * Mỗi mục có một "ngày nghiệp vụ" khác nhau — hợp đồng lọc theo *ngày ký*, phục vụ
 * cộng đồng theo *ngày thực hiện*. Nhãn đó lấy từ backend (`/research-exports`) chứ
 * không viết cứng ở đây, để hai bên không lệch nhau. Ba mục chỉ lưu NĂM thì hiện thêm
 * cảnh báo, vì "từ 01/06 đến 31/03" trên dữ liệu chỉ có năm sẽ ra kết quả rộng hơn
 * người dùng tưởng.
 */
import { useEffect, useState } from 'react';
import { FileSpreadsheet } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { apiGet, apiDownload } from '@/lib/api';

export type ExportKind =
  | 'research-projects'
  | 'publications'
  // m47 — hai mục tách riêng; 'publications' (gộp) giữ lại cho báo cáo tổng kết năm.
  | 'papers'
  | 'patents'
  | 'research-contracts'
  | 'community-services'
  | 'student-mentorships'
  | 'teaching-courses'
  | 'training-certificates'
  | 'staff-activities';

interface KindMeta {
  kind: ExportKind;
  label: string;
  /** Nhãn trường thời gian: "Ngày ký", "Năm công bố"… */
  filter_field: string;
  /** 'year' = dữ liệu gốc chỉ có năm, khoảng ngày bị quy về khoảng năm. */
  granularity: 'date' | 'year';
}

/** Nạp một lần cho cả phiên: danh mục này gần như không đổi. */
let metaCache: KindMeta[] | null = null;

export function ExportExcelButton({ kind }: { kind: ExportKind }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<KindMeta | null>(
    () => metaCache?.find((m) => m.kind === kind) ?? null,
  );

  useEffect(() => {
    if (meta || !open) return;
    let alive = true;
    apiGet<KindMeta[]>('/research-exports')
      .then((rows) => {
        metaCache = rows;
        if (alive) setMeta(rows.find((m) => m.kind === kind) ?? null);
      })
      // Không lấy được nhãn thì vẫn xuất được — chỉ mất phần chú thích.
      .catch(() => {});
    return () => { alive = false; };
  }, [open, kind, meta]);

  async function download() {
    if (from && to && from > to) {
      return toast.error('Ngày bắt đầu phải trước ngày kết thúc');
    }
    setBusy(true);
    try {
      const query: Record<string, string> = {};
      if (from) query.from = from;
      if (to) query.to = to;
      const { blob, filename } = await apiDownload(`/research-exports/${kind}.xlsx`, query);

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      setOpen(false);
      toast.success('Đã tải file Excel');
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <FileSpreadsheet size={16} /> Xuất Excel
      </Button>

      {open && (
        <Modal
          open
          onClose={() => setOpen(false)}
          title="Xuất Excel"
          description={meta?.label}
          footer={
            <>
              <Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>
                Hủy
              </Button>
              <Button onClick={download} loading={busy}>Tải file</Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm text-subink">
              Bỏ trống cả hai ô để xuất <strong>toàn bộ</strong>.
              {meta && <> Khoảng thời gian lọc theo <strong>{meta.filter_field.toLowerCase()}</strong>.</>}
            </p>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Từ ngày">
                <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
              </Field>
              <Field label="Đến ngày">
                <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
              </Field>
            </div>

            {meta?.granularity === 'year' && (from || to) && (
              <div className="rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-sm text-ink">
                Mục này chỉ lưu <strong>năm</strong>, không lưu ngày. Khoảng bạn chọn sẽ được
                quy về <strong>khoảng năm</strong> mà nó phủ — ví dụ 01/06/2024 → 31/03/2025
                lấy cả năm 2024 và 2025.
              </div>
            )}

            <p className="text-xs text-subink">
              File chỉ chứa những bản ghi bạn được xem. Bản ghi thiếu dữ liệu thời gian sẽ
              bị loại khi có lọc, và số lượng bị loại được ghi ở đầu file.
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}
