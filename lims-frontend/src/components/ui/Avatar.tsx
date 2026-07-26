import { useEffect, useState } from 'react';
import { avatarColor, initials } from '@/lib/format';
import { cn } from '@/lib/cn';

export function Avatar({
  name,
  src,
  size = 'md',
  className,
}: {
  name: string;
  /** m30 — URL ảnh đại diện. Hỏng/hết hạn thì tự rơi về chữ cái đầu. */
  src?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const sizes = {
    sm: 'h-7 w-7 text-[11px]',
    md: 'h-9 w-9 text-xs',
    lg: 'h-11 w-11 text-sm',
  };

  // Presigned URL chỉ sống 15 phút; hết hạn thì ảnh lỗi tải → quay về chữ cái đầu
  // thay vì hiện ô ảnh vỡ.
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  const showImage = !!src && !failed;

  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold text-white',
        sizes[size],
        className,
      )}
      style={showImage ? undefined : { backgroundColor: avatarColor(name) }}
      title={name}
    >
      {showImage ? (
        <img
          src={src}
          alt={name}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        initials(name)
      )}
    </div>
  );
}
