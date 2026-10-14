/**
 * Nhập / xuất Excel Thẻ vào PTN — theo file gốc của Văn phòng
 * ("DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN QUÝ …").
 *
 * Nhập luôn qua bước XEM TRƯỚC (dry_run): chọn tệp là backend đọc thử và trả về số
 * dòng sẽ tạo / cập nhật / lỗi; bấm "Nhập" mới ghi thật.
 */
import { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Field, Input, Select } from '@/components/ui/Field';
import { FileDrop } from '@/pages/Documents';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import * as labAccessApi from '@/api/labAccess';
import type { LabAccessImportResult } from '@/api/labAccess';

const XLSX_ACCEPT = '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

const ACTION_LABEL: Record<LabAccessImportResult['items'][number]['action'], [string, BadgeTone]> = {
  create: ['Tạo mới', 'success'],
  update: ['Cập nhật', 'info'],
  unchanged: ['Không đổi', 'neutral'],
};

export function LabAccessImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<LabAccessImportResult | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [committing, setCommitting] = useState(false);

  async function pick(f: File | null) {
    setFile(f);
    setPreview(null);
    if (!f) return;
    setPreviewing(true);
    try {
      setPreview(await labAccessApi.importLabAccessCards(f, true));
    } catch (err) {
      toast.error(describeError(err).title);
      setFile(null);
    } finally {
      setPreviewing(false);
    }
  }

  async function commit() {
    if (!file) return;
    setCommitting(true);
    try {
      const r = await labAccessApi.importLabAccessCards(file, false);
      toast.success(`Đã nhập: ${r.created} tạo mới, ${r.updated} cập nhật`);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setCommitting(false);
    }
  }

  const writes = preview ? preview.created + preview.updated : 0;
  const changed = preview?.items.filter((i) => i.action !== 'unchanged') ?? [];

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Nhập danh sách từ Excel"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={committing}>
            Hủy
          </Button>
          <Button onClick={commit} loading={committing} disabled={!preview || writes === 0 || previewing}>
            {preview ? `Nhập ${writes} dòng` : 'Nhập'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-subink">
          Chọn file theo mẫu <b>"Danh sách sinh viên đã được cấp thẻ vào PTN"</b>. Hệ thống đọc sheet
          TỔNG, đối chiếu theo <b>MSSV</b>: sinh viên đã có sẽ được cập nhật theo file, chưa có sẽ được
          thêm mới. Bản ghi không có trong file được giữ nguyên.
        </p>
        <FileDrop file={file} onSelect={pick} accept={XLSX_ACCEPT} />

        {previewing && <p className="text-sm text-subink">Đang đọc tệp…</p>}

        {preview && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-subink">
                Sheet <b className="text-ink">{preview.sheet}</b> · {preview.total_rows} dòng
              </span>
              <Badge tone="success">{preview.created} tạo mới</Badge>
              <Badge tone="info">{preview.updated} cập nhật</Badge>
              <Badge tone="neutral">{preview.unchanged} không đổi</Badge>
              {preview.errors.length > 0 && <Badge tone="overdue">{preview.errors.length} lỗi</Badge>}
            </div>

            {preview.errors.length > 0 && (
              <div className="rounded-lg border border-overdue/30 bg-overdue/5 p-3">
                <p className="mb-2 text-sm font-medium text-overdue">
                  Các dòng sau sẽ bị bỏ qua — sửa trong file rồi nhập lại:
                </p>
                <ul className="max-h-40 space-y-1 overflow-y-auto text-sm text-ink">
                  {preview.errors.map((e) => (
                    <li key={e.row}>
                      Dòng {e.row}
                      {e.student_code ? ` (MSSV ${e.student_code})` : ''}: {e.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {changed.length > 0 && (
              <div className="max-h-64 overflow-y-auto rounded-lg border border-hairline">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-plate text-left text-xs uppercase text-subink">
                    <tr>
                      <th className="px-3 py-2">Dòng</th>
                      <th className="px-3 py-2">MSSV</th>
                      <th className="px-3 py-2">Sinh viên</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {changed.map((i) => (
                      <tr key={i.row} className="border-t border-hairline">
                        <td className="px-3 py-1.5 text-subink">{i.row}</td>
                        <td className="px-3 py-1.5">{i.student_code}</td>
                        <td className="px-3 py-1.5">{i.student_name}</td>
                        <td className="px-3 py-1.5 text-right">
                          <Badge tone={ACTION_LABEL[i.action][1]}>{ACTION_LABEL[i.action][0]}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

const QUARTERS = ['I', 'II', 'III', 'IV'];

export function LabAccessExportModal({
  filters,
  onClose,
}: {
  filters: { q?: string; supervisor_name?: string };
  onClose: () => void;
}) {
  const toast = useToast();
  const now = new Date();
  const [quarter, setQuarter] = useState(Math.floor(now.getMonth() / 3) + 1);
  const [year, setYear] = useState(String(now.getFullYear()));
  const [busy, setBusy] = useState(false);
  const filtered = !!(filters.q || filters.supervisor_name);

  async function download() {
    const y = Number(year);
    if (!Number.isInteger(y) || y < 2000 || y > 2100) return toast.error('Năm không hợp lệ');
    setBusy(true);
    try {
      await labAccessApi.exportLabAccessCards({ ...filters, quarter, year: y });
      onClose();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title="Xuất Excel"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Hủy
          </Button>
          <Button onClick={download} loading={busy}>
            Tải file
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-subink">
          File theo đúng mẫu "Danh sách đã được cấp thẻ vào PTN": sheet tổng và mỗi giáo viên hướng dẫn một
          sheet. Quý/năm dùng cho tiêu đề và tên sheet.
          {filtered && ' Chỉ gồm các dòng khớp bộ lọc đang áp dụng.'}
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Quý">
            <Select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
              {QUARTERS.map((q, i) => (
                <option key={q} value={i + 1}>
                  Quý {q}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Năm">
            <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}
