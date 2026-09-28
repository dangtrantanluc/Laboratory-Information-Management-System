import { useState } from 'react';
import { Star } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import type { HrProfile } from '@/types';
import * as hrApi from '@/api/hr';
import * as usersApi from '@/api/users';

interface Props {
  profile: HrProfile;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Sửa phòng công tác của một hồ sơ (m50).
 *
 * Tách khỏi HrProfileView vì đây là màn hình có trạng thái riêng (tập phòng đã chọn +
 * phòng nào là chính), và HrProfileView đã sát trần 800 dòng.
 *
 * HAI TRỤC, MỘT DANH SÁCH: tick = có công tác ở phòng đó; ngôi sao = phòng chính. API
 * nhận một mảng có thứ tự, phần tử đầu là phòng chính — nên lúc gửi, phòng chính được
 * đẩy lên đầu. Bỏ tick phòng đang là chính thì phòng còn lại đầu tiên lên thay, chứ
 * không để hồ sơ có phòng mà không có phòng chính.
 */
export function ProfileDepartmentsModal({ profile, onClose, onSaved }: Props) {
  const toast = useToast();
  const { data: depts, loading } = useAsync(() => usersApi.listDepartments(), []);
  const hienCo = profile.departments ?? [];
  const [chon, setChon] = useState<string[]>(hienCo.map((d) => d.id));
  const [chinh, setChinh] = useState<string>(
    hienCo.find((d) => d.is_primary)?.id ?? hienCo[0]?.id ?? '',
  );
  const [submitting, setSubmitting] = useState(false);

  function toggle(id: string) {
    setChon((truoc) => {
      const sau = truoc.includes(id) ? truoc.filter((x) => x !== id) : [...truoc, id];
      // Phòng chính phải luôn nằm trong tập đã chọn.
      if (!sau.includes(chinh)) setChinh(sau[0] ?? '');
      else if (!chinh && sau.length) setChinh(sau[0]);
      return sau;
    });
  }

  async function submit() {
    setSubmitting(true);
    try {
      // Phòng chính lên đầu — đó là cách API đọc "phòng nào là chính".
      const sapXep = chinh ? [chinh, ...chon.filter((x) => x !== chinh)] : chon;
      await hrApi.updateProfile(profile.id, { department_ids: sapXep });
      onSaved();
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
      title="Phòng công tác"
      description="Tick những phòng người này công tác. Kiêm nhiệm thì tick nhiều phòng, rồi chọn một phòng chính."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      {loading ? (
        <p className="text-sm text-subink">Đang tải danh sách phòng…</p>
      ) : (
        <ul className="flex flex-col divide-y divide-hairline">
          {(depts?.data ?? []).map((d) => {
            const daChon = chon.includes(d.id);
            return (
              <li key={d.id} className="flex items-center gap-3 py-2">
                <input
                  type="checkbox"
                  id={`dept-${d.id}`}
                  checked={daChon}
                  onChange={() => toggle(d.id)}
                  className="size-4 shrink-0"
                />
                <label htmlFor={`dept-${d.id}`} className="flex-1 text-sm text-ink">
                  {d.name}
                </label>
                {daChon && (
                  <button
                    type="button"
                    onClick={() => setChinh(d.id)}
                    aria-pressed={chinh === d.id}
                    aria-label={`Đặt ${d.name} làm phòng chính`}
                    title="Phòng chính"
                    className="inline-flex shrink-0 items-center gap-1 text-xs text-subink hover:text-ink"
                  >
                    <Star
                      size={14}
                      className={chinh === d.id ? 'fill-stem text-stem' : ''}
                    />
                    {chinh === d.id && <span className="text-stem">chính</span>}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}
