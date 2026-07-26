import { useRef, useState } from 'react';
import { Camera, Trash2 } from 'lucide-react';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import * as authApi from '@/api/auth';

const MAX_MB = 2;
const ACCEPT = 'image/jpeg,image/png,image/webp';

/**
 * Ảnh đại diện (m30) — tải lên MinIO, DB chỉ giữ object key.
 *
 * Kiểm tra kích thước/định dạng ở client chỉ để phản hồi nhanh; server vẫn kiểm lại
 * bằng magic bytes (đổi đuôi file không qua mặt được).
 */
export function AvatarUploader() {
  const { user, refreshMe } = useAuth();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  // Xem trước ngay sau khi chọn file, không phải chờ tải xong.
  const [preview, setPreview] = useState<string | null>(null);

  async function onPick(file: File | undefined) {
    if (!file) return;
    if (!ACCEPT.split(',').includes(file.type)) {
      return toast.error('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP');
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return toast.error(`Ảnh vượt quá ${MAX_MB}MB`);
    }

    const localUrl = URL.createObjectURL(file);
    setPreview(localUrl);
    setBusy(true);
    try {
      await authApi.uploadAvatar(file);
      await refreshMe();
      toast.success('Đã cập nhật ảnh đại diện');
    } catch (err) {
      setPreview(null);
      const { title, description } = describeError(err);
      toast.error(title, description);
    } finally {
      setBusy(false);
      URL.revokeObjectURL(localUrl);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function onRemove() {
    setBusy(true);
    try {
      await authApi.removeAvatar();
      setPreview(null);
      await refreshMe();
      toast.success('Đã gỡ ảnh đại diện');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  const currentSrc = preview ?? user?.avatar_url ?? null;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative">
        <Avatar
          name={user?.full_name ?? '—'}
          src={currentSrc}
          size="lg"
          className="h-24 w-24 text-2xl ring-2 ring-hairline"
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          aria-label="Đổi ảnh đại diện"
          className="absolute -bottom-1 -right-1 flex h-9 w-9 items-center justify-center rounded-full border-2 border-surface bg-blueberry text-white shadow-sm transition-colors hover:bg-blueberry/90 disabled:opacity-60"
        >
          <Camera size={16} />
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0])}
      />

      <div className="flex flex-wrap justify-center gap-2">
        <Button size="sm" variant="secondary" loading={busy} onClick={() => inputRef.current?.click()}>
          <Camera size={14} /> Đổi ảnh
        </Button>
        {user?.avatar_url && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={onRemove}>
            <Trash2 size={14} /> Gỡ ảnh
          </Button>
        )}
      </div>
      <p className="text-center text-[11px] text-stem">JPG, PNG hoặc WEBP · tối đa {MAX_MB}MB</p>
    </div>
  );
}
