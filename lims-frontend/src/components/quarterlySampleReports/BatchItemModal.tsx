/**
 * Nhập NHIỀU mẫu một lần.
 *
 * Mẫu thường về theo lô: cùng ngày nhận, cùng loại mẫu, cùng bộ chỉ tiêu, chỉ khác mã
 * mẫu và số lượng. Nên phần chung chọn MỘT lần ở trên, bên dưới chỉ gõ mã + số lượng:
 * - Enter ở ô mã mẫu → sang dòng kế (tự thêm dòng ở cuối).
 * - Dán một cột mã mẫu từ Excel (kèm cột số lượng bên cạnh nếu có) vào ô mã mẫu → tự tách
 *   thành nhiều dòng.
 * Dòng nào khác ngày nhận thì sửa ngày ngay trên dòng đó.
 *
 * Lưu là tất cả hoặc không dòng nào (backend); dòng lỗi được tô đỏ kèm lý do.
 */
import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { useToast } from '@/context/ToastContext';
import { ApiError } from '@/lib/api';
import { describeError } from '@/lib/errors';
import { TEST_MATRIX_LABELS, type TestMatrix } from '@/types';
import * as api from '@/api/quarterlySampleReports';
import { CriteriaPicker, toggleCriterion, type SelectedCriteria } from './CriteriaPicker';

const MATRICES = Object.keys(TEST_MATRIX_LABELS) as TestMatrix[];
const INITIAL_ROWS = 5;

interface Row {
  key: number;
  code: string;
  qty: string;
  /** '' = theo ngày nhận chung của lô. */
  date: string;
  note: string;
}

let seq = 0;
const newRow = (over: Partial<Row> = {}): Row => ({ key: ++seq, code: '', qty: '1', date: '', note: '', ...over });

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function BatchItemModal({
  report,
  onClose,
  onSaved,
}: {
  report: api.QuarterlyReport;
  onClose: () => void;
  onSaved: (count: number) => void;
}) {
  const toast = useToast();
  const bounds = api.quarterBounds(report.year, report.quarter);
  const today = todayIso();
  const maxDate = bounds.end < today ? bounds.end : today;

  const [sharedDate, setSharedDate] = useState(maxDate);
  const [matrix, setMatrix] = useState<TestMatrix>('soil');
  const [matrixOther, setMatrixOther] = useState('');
  const [selected, setSelected] = useState<SelectedCriteria>(new Map());
  const [extra, setExtra] = useState('');
  const [rows, setRows] = useState<Row[]>(() => Array.from({ length: INITIAL_ROWS }, () => newRow()));
  const [errors, setErrors] = useState<Map<number, string>>(new Map());
  const [saving, setSaving] = useState(false);
  const codeRefs = useRef(new Map<number, HTMLInputElement>());

  const filled = rows.filter((r) => r.code.trim());
  const dupCodes = (() => {
    const seen = new Map<string, number>();
    for (const r of filled) seen.set(r.code.trim(), (seen.get(r.code.trim()) ?? 0) + 1);
    return new Set([...seen].filter(([, n]) => n > 1).map(([c]) => c));
  })();

  function patch(key: number, p: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...p } : r)));
    if (errors.has(key)) {
      setErrors((prev) => {
        const next = new Map(prev);
        next.delete(key);
        return next;
      });
    }
  }

  function focusCode(key: number) {
    // Đợi React vẽ dòng mới xong mới focus được.
    requestAnimationFrame(() => codeRefs.current.get(key)?.focus());
  }

  function addRow() {
    const r = newRow();
    setRows((prev) => [...prev, r]);
    focusCode(r.key);
  }

  function onCodeKeyDown(e: KeyboardEvent<HTMLInputElement>, idx: number) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const next = rows[idx + 1];
    if (next) focusCode(next.key);
    else addRow();
  }

  /** Dán nhiều dòng (một cột mã, hoặc cột mã + cột số lượng từ Excel) → tách thành nhiều dòng. */
  function onCodePaste(e: ClipboardEvent<HTMLInputElement>, idx: number) {
    const text = e.clipboardData.getData('text');
    if (!/[\n\t]/.test(text.trim())) return; // một giá trị đơn — để trình duyệt dán như thường
    e.preventDefault();
    const parsed = text
      .split(/\r?\n/)
      .map((line) => line.split('\t').map((c) => c.trim()))
      .filter((cells) => cells[0])
      .map(([code, qty]) => ({ code, qty: qty && /^\d+$/.test(qty) && Number(qty) >= 1 ? qty : '1' }));
    setRows((prev) => {
      const next = [...prev];
      parsed.forEach((p, i) => {
        const at = idx + i;
        next[at] = next[at] ? { ...next[at], ...p } : newRow(p);
      });
      return next;
    });
    toast.success(`Đã dán ${parsed.length} mã mẫu`);
  }

  function removeRow(key: number) {
    setRows((prev) => (prev.length > 1 ? prev.filter((r) => r.key !== key) : [newRow()]));
  }

  function changeMatrix(m: TestMatrix) {
    // Chỉ tiêu gắn với loại mẫu — đổi sang loại khác thì bỏ các chỉ tiêu đã chọn.
    if (m !== matrix && m !== 'other' && selected.size > 0) setSelected(new Map());
    setMatrix(m);
  }

  async function submit() {
    if (filled.length === 0) return toast.error('Nhập ít nhất một mã mẫu');
    if (matrix === 'other' && !matrixOther.trim()) return toast.error('Ghi rõ loại mẫu khác');
    if (selected.size === 0 && !extra.trim()) return toast.error('Chọn ít nhất một chỉ tiêu phân tích');
    const local = new Map<number, string>();
    for (const r of filled) {
      const q = Number(r.qty);
      const d = r.date || sharedDate;
      if (!Number.isInteger(q) || q < 1) local.set(r.key, 'Số lượng phải là số nguyên ≥ 1');
      else if (!d || d < bounds.start || d > bounds.end)
        local.set(r.key, `Ngày nhận phải trong ${api.periodLabel(report.year, report.quarter)}`);
    }
    if (local.size) {
      setErrors(local);
      return toast.error(`${local.size} dòng chưa hợp lệ`);
    }
    const items: api.QuarterlyItemBody[] = filled.map((r) => ({
      sample_code: r.code.trim(),
      received_date: r.date || sharedDate,
      matrix,
      matrix_other: matrix === 'other' ? matrixOther.trim() : null,
      quantity: Number(r.qty),
      test_parameter_ids: [...selected.keys()],
      extra_criteria: extra.trim() || null,
      note: r.note.trim() || null,
    }));
    setSaving(true);
    try {
      await api.createItemsBatch(report.id, items);
      onSaved(items.length);
    } catch (err) {
      // Lỗi theo dòng (details[].row đánh số từ 1 trên danh sách đã gửi) → tô đúng dòng.
      if (err instanceof ApiError && Array.isArray(err.details)) {
        const byRow = new Map<number, string>();
        for (const d of err.details as api.BatchRowError[]) {
          const row = filled[d.row - 1];
          if (row) byRow.set(row.key, d.message);
        }
        setErrors(byRow);
      }
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={`Nhập nhiều mẫu — ${api.periodLabel(report.year, report.quarter)}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button onClick={submit} loading={saving} disabled={filled.length === 0}>
            Lưu {filled.length || ''} mẫu
          </Button>
        </>
      }
    >
      <FormBody>
        <FormSection title="Thông tin chung cho cả lô">
          <Field label="Ngày nhận mẫu" required hint="Dòng nào khác ngày thì sửa trên dòng đó">
            <Input
              type="date"
              value={sharedDate}
              min={bounds.start}
              max={maxDate}
              onChange={(e) => setSharedDate(e.target.value)}
            />
          </Field>
          <Field label="Loại mẫu" required>
            <Select value={matrix} onChange={(e) => changeMatrix(e.target.value as TestMatrix)}>
              {MATRICES.map((m) => (
                <option key={m} value={m}>
                  {TEST_MATRIX_LABELS[m]}
                </option>
              ))}
            </Select>
          </Field>
          {matrix === 'other' && (
            <Field label="Loại mẫu khác" required className="md:col-span-2">
              <Input value={matrixOther} onChange={(e) => setMatrixOther(e.target.value)} placeholder="Ghi rõ loại mẫu" />
            </Field>
          )}
          <Field label="Chỉ tiêu phân tích" required className="md:col-span-2">
            <CriteriaPicker
              matrix={matrix}
              selected={selected}
              onToggle={(id, name) => setSelected((prev) => toggleCriterion(prev, id, name))}
            />
          </Field>
          <Field
            label="Chỉ tiêu ngoài danh mục"
            hint="Cách nhau bằng dấu phẩy — vd: Tro, Đạm tổng số"
            className="md:col-span-2"
          >
            <Input value={extra} onChange={(e) => setExtra(e.target.value)} />
          </Field>
        </FormSection>

        <FormSection title={`Danh sách mẫu (${filled.length})`}>
          <div className="flex flex-col gap-2 md:col-span-2">
            <p className="text-xs text-subink">
              Enter để xuống dòng mới. Có sẵn danh sách trong Excel: copy cột mã mẫu (kèm cột số lượng bên cạnh nếu
              có) rồi dán vào ô mã mẫu đầu tiên.
            </p>
            <div className="overflow-x-auto">
              <div className="min-w-[640px]">
                <div className="grid grid-cols-[32px_minmax(140px,1fr)_84px_150px_minmax(140px,1fr)_36px] gap-2 border-b border-hairline pb-1.5 text-xs font-medium uppercase text-subink">
                  <span className="text-center">#</span>
                  <span>Mã số mẫu</span>
                  <span>Số lượng</span>
                  <span>Ngày nhận</span>
                  <span>Ghi chú</span>
                  <span />
                </div>
                {rows.map((r, idx) => {
                  const err = errors.get(r.key);
                  const dup = r.code.trim() && dupCodes.has(r.code.trim());
                  return (
                    <div key={r.key} className="border-b border-hairline py-1.5 last:border-0">
                      <div className="grid grid-cols-[32px_minmax(140px,1fr)_84px_150px_minmax(140px,1fr)_36px] items-center gap-2">
                        <span className="text-center text-sm text-subink">{idx + 1}</span>
                        <Input
                          ref={(el) => {
                            if (el) codeRefs.current.set(r.key, el);
                            else codeRefs.current.delete(r.key);
                          }}
                          value={r.code}
                          invalid={!!err}
                          placeholder="vd: 26N265"
                          onChange={(e) => patch(r.key, { code: e.target.value })}
                          onKeyDown={(e) => onCodeKeyDown(e, idx)}
                          onPaste={(e) => onCodePaste(e, idx)}
                        />
                        <Input
                          type="number"
                          min={1}
                          value={r.qty}
                          onChange={(e) => patch(r.key, { qty: e.target.value })}
                        />
                        <Input
                          type="date"
                          value={r.date || sharedDate}
                          min={bounds.start}
                          max={maxDate}
                          onChange={(e) => patch(r.key, { date: e.target.value === sharedDate ? '' : e.target.value })}
                        />
                        <Input value={r.note} onChange={(e) => patch(r.key, { note: e.target.value })} />
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Xóa dòng ${idx + 1}`}
                          onClick={() => removeRow(r.key)}
                        >
                          <Trash2 size={15} />
                        </Button>
                      </div>
                      {(err || dup) && (
                        <p className={`mt-1 pl-10 text-xs ${err ? 'text-overdue' : 'text-warning'}`}>
                          <AlertTriangle size={12} className="mr-1 inline" />
                          {err ?? 'Mã mẫu trùng với dòng khác trong lô — kiểm tra có nhập trùng không'}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            <div>
              <Button variant="secondary" size="sm" onClick={addRow}>
                <Plus size={14} /> Thêm dòng
              </Button>
            </div>
          </div>
        </FormSection>
      </FormBody>
    </Modal>
  );
}
