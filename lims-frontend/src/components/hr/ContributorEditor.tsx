import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Field, Input, Select } from '@/components/ui/Field';
import type { UserListItem } from '@/types';

/**
 * Một người tham gia (thành viên đề tài / tác giả bài báo):
 * HOẶC nội bộ (user_id) HOẶC ngoài hệ thống (external_name) — không cả hai (BE: INVALID_AUTHOR).
 */
export interface ContributorRow {
  mode: 'internal' | 'external';
  user_id: string;
  external_name: string;
  /** Vai trò trong đề tài (members) hoặc bỏ qua với tác giả. */
  role?: string;
  /** Thứ tự tác giả (publications). */
  author_order?: number;
  is_corresponding?: boolean;
}

export function emptyContributor(order?: number): ContributorRow {
  return {
    mode: 'internal',
    user_id: '',
    external_name: '',
    role: 'member',
    author_order: order,
    is_corresponding: false,
  };
}

const ROLE_OPTIONS = [
  { value: 'lead', label: 'Chủ nhiệm' },
  { value: 'member', label: 'Thành viên' },
  { value: 'secretary', label: 'Thư ký' },
];

export function ContributorEditor({
  rows,
  onChange,
  users,
  variant,
}: {
  rows: ContributorRow[];
  onChange: (rows: ContributorRow[]) => void;
  users: UserListItem[];
  /** 'member' = đề tài (có role); 'author' = bài báo (có thứ tự + corresponding). */
  variant: 'member' | 'author';
}) {
  function update(i: number, patch: Partial<ContributorRow>) {
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function add() {
    const nextOrder = variant === 'author' ? rows.length + 1 : undefined;
    onChange([...rows, emptyContributor(nextOrder)]);
  }
  function remove(i: number) {
    onChange(rows.filter((_, idx) => idx !== i));
  }

  return (
    <div className="flex flex-col gap-3">
      {rows.map((r, i) => (
        <div key={i} className="rounded-lg border border-hairline p-3">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Nguồn" className="w-[150px]">
              <Select
                value={r.mode}
                onChange={(e) => update(i, { mode: e.target.value as ContributorRow['mode'] })}
              >
                <option value="internal">Nội bộ</option>
                <option value="external">Ngoài hệ thống</option>
              </Select>
            </Field>

            {r.mode === 'internal' ? (
              <Field label="Người dùng" className="min-w-[200px] flex-1">
                <Select value={r.user_id} onChange={(e) => update(i, { user_id: e.target.value })}>
                  <option value="">— Chọn —</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field label="Tên người ngoài" className="min-w-[200px] flex-1">
                <Input
                  value={r.external_name}
                  onChange={(e) => update(i, { external_name: e.target.value })}
                  placeholder="GS. Smith (ĐH ngoài)"
                />
              </Field>
            )}

            {variant === 'member' ? (
              <Field label="Vai trò" className="w-[160px]">
                <Select value={r.role ?? 'member'} onChange={(e) => update(i, { role: e.target.value })}>
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <>
                <Field label="Thứ tự" className="w-[90px]">
                  <Input
                    type="number"
                    min={1}
                    value={r.author_order ?? i + 1}
                    onChange={(e) => update(i, { author_order: Number(e.target.value) })}
                  />
                </Field>
                <label className="flex h-10 items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={!!r.is_corresponding}
                    onChange={(e) => update(i, { is_corresponding: e.target.checked })}
                  />
                  Liên hệ
                </label>
              </>
            )}

            <Button variant="ghost" size="sm" onClick={() => remove(i)} className="h-10">
              <Trash2 size={15} />
            </Button>
          </div>
        </div>
      ))}
      <Button variant="secondary" size="sm" onClick={add} className="w-fit">
        <Plus size={14} /> Thêm {variant === 'author' ? 'tác giả' : 'thành viên'}
      </Button>
    </div>
  );
}

/** Chuyển ContributorRow[] → payload members cho API đề tài. */
export function toMembers(rows: ContributorRow[]) {
  return rows.map((r) => ({
    user_id: r.mode === 'internal' ? r.user_id || null : null,
    external_name: r.mode === 'external' ? r.external_name.trim() || null : null,
    role_in_project: r.role ?? 'member',
  }));
}

/** Chuyển ContributorRow[] → payload authors cho API bài báo. */
export function toAuthors(rows: ContributorRow[]) {
  return rows.map((r, i) => ({
    user_id: r.mode === 'internal' ? r.user_id || null : null,
    external_name: r.mode === 'external' ? r.external_name.trim() || null : null,
    author_order: r.author_order ?? i + 1,
    is_corresponding: !!r.is_corresponding,
  }));
}

/** Validate cơ bản trước khi gửi (mỗi dòng phải có đúng 1 nguồn). */
export function validateContributors(rows: ContributorRow[]): string | null {
  if (rows.length === 0) return 'Cần ít nhất một người tham gia';
  for (const r of rows) {
    if (r.mode === 'internal' && !r.user_id) return 'Chọn người dùng cho thành viên nội bộ';
    if (r.mode === 'external' && !r.external_name.trim())
      return 'Nhập tên cho người ngoài hệ thống';
  }
  return null;
}
