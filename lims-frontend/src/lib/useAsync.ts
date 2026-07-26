import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Gọi API có chống race condition (R5.2).
 *
 * Bản cũ có cờ `active`, nhưng `reload()` VỨT BỎ hàm cleanup mà `run()` trả về →
 * hai request chồng nhau đều còn "active", cái về sau ghi đè cái về trước. Với
 * LIMS, đó là hiển thị sai trạng thái mẫu/kết quả thử nghiệm.
 *
 * Bản này dùng số thứ tự tăng dần: chỉ response của lần gọi MỚI NHẤT được ghi vào
 * state. Kèm AbortController để huỷ thật ở tầng mạng, không chỉ phớt lờ kết quả.
 *
 * Tương thích ngược: `signal` là tham số OPTIONAL nên 135 lượt gọi hiện có không
 * phải sửa gì. Chỗ nào muốn huỷ thật thì truyền tiếp xuống `apiGet(path, { signal })`.
 */
export function useAsync<T>(fn: (signal?: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const seqRef = useRef(0);
  const acRef = useRef<AbortController | null>(null);

  const run = useCallback(() => {
    acRef.current?.abort(); // huỷ lần gọi trước còn dang dở
    const ac = new AbortController();
    acRef.current = ac;
    const seq = ++seqRef.current;

    setLoading(true);
    setError(null);
    fn(ac.signal)
      .then((d) => {
        if (seq === seqRef.current) setData(d);
      })
      .catch((e) => {
        if (seq !== seqRef.current) return;
        // Huỷ chủ động không phải lỗi — đừng hiện thông báo đỏ cho người dùng.
        if (e?.name === 'AbortError') return;
        setError(e);
      })
      .finally(() => {
        if (seq === seqRef.current) setLoading(false);
      });

    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => run(), [run]);

  return { data, loading, error, reload: run };
}
