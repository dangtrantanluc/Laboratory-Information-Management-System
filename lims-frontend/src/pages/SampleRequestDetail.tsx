import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Plus, ClipboardList } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Textarea, Select } from '@/components/ui/Field';
import { SampleStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canCreateSample } from '@/lib/rbac';
import * as samplesApi from '@/api/samples';

export function SampleRequestDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [addOpen, setAddOpen] = useState(false);

  const { data, loading, reload } = useAsync(() => samplesApi.getRequest(id), [id]);

  if (loading) return <LoadingState />;
  if (!data)
    return (
      <Card>
        <EmptyState title="Không tìm thấy phiếu" />
      </Card>
    );

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/samples')}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Danh sách phiếu
      </button>

      <PageHeader
        title={data.request_code}
        description={`Khách: ${data.customer?.name ?? data.sender_name} · ${data.department_name ?? '—'}`}
        icon={<ClipboardList size={20} />}
        actions={
          canCreateSample(user) ? (
            <Button onClick={() => setAddOpen(true)}>
              <Plus size={16} /> Thêm mẫu
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="Thông tin phiếu" />
          <CardBody className="flex flex-col gap-2.5 text-sm">
            <Row label="Người gửi" value={data.sender_name} />
            <Row label="Khách hàng" value={data.customer?.name ?? '—'} />
            <Row label="Liên hệ" value={data.customer?.contact ?? '—'} />
            <Row label="Người tiếp nhận" value={data.received_by_name ?? '—'} />
            <Row label="Ngày nhận" value={formatDateTime(data.received_at)} />
            <Row label="Ghi chú" value={data.note ?? '—'} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title={`Danh sách mẫu (${data.samples.length})`} />
          <CardBody className="p-0">
            {data.samples.length === 0 ? (
              <EmptyState
                title="Chưa có mẫu"
                description="Thêm mẫu vào phiếu để bắt đầu quy trình thử nghiệm."
              />
            ) : (
              <ul className="flex flex-col divide-y divide-hairline">
                {data.samples.map((s) => (
                  <li
                    key={s.id}
                    onClick={() => navigate(`/samples/sample/${s.id}`)}
                    className="flex cursor-pointer items-center justify-between gap-3 px-5 py-3.5 hover:bg-plate/60"
                  >
                    <div className="min-w-0">
                      <p className="font-semibold text-ink">{s.sample_code}</p>
                      <p className="text-xs text-subink">Hạn {formatDate(s.deadline_at)}</p>
                    </div>
                    <SampleStatusBadge status={s.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>

      {addOpen && (
        <AddSampleModal
          requestId={id}
          onClose={() => setAddOpen(false)}
          onAdded={() => {
            setAddOpen(false);
            reload();
            toast.success('Đã thêm mẫu');
          }}
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="shrink-0 text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function AddSampleModal({
  requestId,
  onClose,
  onAdded,
}: {
  requestId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');
  const [condition, setCondition] = useState('');
  const [conditionNote, setConditionNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!description.trim()) return toast.error('Nhập mô tả mẫu');
    if (!deadline) return toast.error('Chọn hạn hoàn thành');
    if (condition === 'not_acceptable' && !conditionNote.trim())
      return toast.error('Nhập lý do khi tình trạng không đạt');
    setSubmitting(true);
    try {
      await samplesApi.addSample(requestId, {
        description: description.trim(),
        deadline_at: new Date(deadline).toISOString(),
        condition_status: condition || null,
        condition_note: conditionNote || null,
      });
      onAdded();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Thêm mẫu vào phiếu"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Thêm mẫu
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Mô tả mẫu" required>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="vd: Mẫu nước thải đầu vào"
          />
        </Field>
        <Field label="Hạn hoàn thành (deadline)" required>
          <Input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </Field>
        <Field label="Tình trạng khi nhận">
          <Select value={condition} onChange={(e) => setCondition(e.target.value)}>
            <option value="">— Chưa ghi nhận —</option>
            <option value="acceptable">Đạt điều kiện</option>
            <option value="not_acceptable">Không đạt điều kiện</option>
          </Select>
        </Field>
        {condition === 'not_acceptable' && (
          <Field label="Lý do không đạt" required>
            <Input value={conditionNote} onChange={(e) => setConditionNote(e.target.value)} placeholder="vd: Bao bì rách" />
          </Field>
        )}
      </div>
    </Modal>
  );
}
