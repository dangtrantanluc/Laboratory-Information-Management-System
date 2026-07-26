import { useEffect, useState } from 'react';

/**
 * Trì hoãn giá trị cho tới khi người dùng ngừng gõ `ms` mili-giây (R5.3).
 *
 * Không có nó, mỗi ký tự trong ô tìm kiếm là một request: gõ "chloroform" = 10
 * request. 20 người cùng tìm giờ cao điểm = 200 request trong vài giây, và các
 * response về không đúng thứ tự nên kết quả của "chlo" đè lên "chloroform".
 *
 * Dùng: ô nhập vẫn bind `q` (gõ mượt), còn useAsync phụ thuộc `useDebounced(q)`.
 */
export function useDebounced<T>(value: T, ms = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
