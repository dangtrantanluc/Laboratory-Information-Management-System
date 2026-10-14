/**
 * Thêm / sửa một dòng mẫu trong báo cáo quý.
 *
 * Chỉ tiêu: chọn từ danh mục của đúng loại mẫu (CriteriaPicker), cộng ô "chỉ tiêu ngoài
 * danh mục" cho những chỉ tiêu chưa có (vd "Tro"). Nhập cả lô: BatchItemModal.
 */
import { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { TEST_MATRIX_LABELS, type TestMatrix } from '@/types';
import * as api from '@/api/quarterlySampleReports';
import { CriteriaPicker, toggleCriterion } from './CriteriaPicker';

const MATRICES = Object.keys(TEST_MATRIX_LABELS) as TestMatrix[];

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function SampleItemModal({
  report,
  item,
  onClose,
  onSaved,
}: {
  report: api.QuarterlyReport;
  item?: api.QuarterlyReportItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const bounds = api.quarterBounds(report.year, report.quarter);
  const today = todayIso();
  const maxDate = bounds.end < today ? bounds.end : today;

  const [sampleCode, setSampleCode] = useState(item?.sample_code ?? '');
  const [receivedDate, setReceivedDate] = useState(item?.received_date ?? maxDate);
  const [matrix, setMatrix] = useState<TestMatrix>(item?.matrix ?? 'soil');
  const [matrixOther, setMatrixOther] = useState(item?.matrix_other ?? '');
  const [quantity, setQuantity] = useState(String(item?.quantity ?? 1));
  // id → tên, giữ cả những chỉ tiêu đã chọn nhưng không nằm trong kết quả tìm hiện tại.
  const [selected, setSelected] = useState<Map<string, string>>(
    () =>
      new Map(
        (item?.criteria ?? [])
          .filter((c) => c.test_parameter_id)
          .map((c) => [c.test_parameter_id as string, c.name]),
      ),
  );
  const [extra, setExtra] = useState(item?.extra_criteria ?? '');
  const [note, setNote] = useState(item?.note ?? '');
  const [saving, setSaving] = useState(false);

  function changeMatrix(m: TestMatrix) {
    // Chỉ tiêu gắn với loại mẫu — đổi loại mẫu thì bỏ các chỉ tiêu đã chọn của loại cũ.
    if (m !== matrix && m !== 'other' && selected.size > 0) setSelected(new Map());
    setMatrix(m);
  }

  function toggle(id: string, name: string) {
    setSelected((prev) => toggleCriterion(prev, id, name));
  }

  async function submit() {
    const qty = Number(quantity);
    if (!sampleCode.trim()) return toast.error('Nhập mã số mẫu');
    if (!receivedDate) return toast.error('Chọn ngày nhận mẫu');
    if (receivedDate < bounds.start || receivedDate > bounds.end)
      return toast.error(`Ngày nhận mẫu phải trong ${api.periodLabel(report.year, report.quarter)}`);
    if (matrix === 'other' && !matrixOther.trim()) return toast.error('Ghi rõ loại mẫu khác');
    if (!Number.isInteger(qty) || qty < 1) return toast.error('Số lượng mẫu phải là số nguyên ≥ 1');
    if (selected.size === 0 && !extra.trim()) return toast.error('Chọn ít nhất một chỉ tiêu phân tích');
    const body: api.QuarterlyItemBody = {
      sample_code: sampleCode.trim(),
      received_date: receivedDate,
      matrix,
      matrix_other: matrix === 'other' ? matrixOther.trim() : null,
      quantity: qty,
      test_parameter_ids: [...selected.keys()],
      extra_criteria: extra.trim() || null,
      note: note.trim() || null,
    };
    setSaving(true);
    try {
      if (item) await api.updateItem(report.id, item.id, body);
      else await api.createItem(report.id, body);
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={item ? `Sửa mẫu ${item.sample_code}` : 'Thêm mẫu'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button onClick={submit} loading={saving}>
            {item ? 'Lưu' : 'Thêm'}
          </Button>
        </>
      }
    >
      <FormBody>
        <FormSection title="Mẫu">
          <Field label="Mã số mẫu" required>
            <Input value={sampleCode} onChange={(e) => setSampleCode(e.target.value)} placeholder="vd: 26N265" />
          </Field>
          <Field label="Ngày nhận mẫu" required hint={api.periodLabel(report.year, report.quarter)}>
            <Input
              type="date"
              value={receivedDate}
              min={bounds.start}
              max={maxDate}
              onChange={(e) => setReceivedDate(e.target.value)}
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
          <Field label="Số lượng mẫu" required hint="Số mẫu vật nhận được, không phải số chỉ tiêu">
            <Input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </Field>
          {matrix === 'other' && (
            <Field label="Loại mẫu khác" required className="md:col-span-2">
              <Input value={matrixOther} onChange={(e) => setMatrixOther(e.target.value)} placeholder="Ghi rõ loại mẫu" />
            </Field>
          )}
        </FormSection>

        <FormSection title="Chỉ tiêu phân tích">
          <div className="md:col-span-2">
            <CriteriaPicker matrix={matrix} selected={selected} onToggle={toggle} />
          </div>
          <Field
            label="Chỉ tiêu ngoài danh mục"
            hint="Chỉ tiêu chưa có trong danh mục, cách nhau bằng dấu phẩy — vd: Tro, Đạm tổng số"
            className="md:col-span-2"
          >
            <Input value={extra} onChange={(e) => setExtra(e.target.value)} />
          </Field>
          <Field label="Ghi chú" className="md:col-span-2">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}
