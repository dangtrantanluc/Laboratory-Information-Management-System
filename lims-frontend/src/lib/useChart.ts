import { useDown, useUp } from './useMediaQuery';

/**
 * Chiều cao biểu đồ theo bề ngang màn hình.
 *
 * Recharts `<ResponsiveContainer>` chỉ co giãn chiều NGANG; chiều cao phải tự
 * quyết định. Cùng một `height={280}` sẽ quá cao trên điện thoại và quá dẹt
 * trên màn 2K.
 */
export function useChartHeight(): number {
  const isMobile = useDown('sm');
  const isHuge = useUp('3xl');
  return isMobile ? 200 : isHuge ? 360 : 280;
}

/** Cấu hình trục/legend thu gọn khi màn hẹp — nhãn tiếng Việt rất dễ chồng nhau. */
export function useChartCompact() {
  const isMobile = useDown('sm');
  return {
    isMobile,
    /** Rải vào <XAxis {...xAxis} /> */
    xAxis: {
      tick: { fontSize: isMobile ? 10 : 12 },
      angle: isMobile ? -40 : 0,
      textAnchor: isMobile ? ('end' as const) : ('middle' as const),
      height: isMobile ? 56 : 30,
      interval: isMobile ? ('preserveStartEnd' as const) : 0,
    },
    /** Rải vào <YAxis {...yAxis} /> */
    yAxis: {
      tick: { fontSize: isMobile ? 10 : 12 },
      width: isMobile ? 32 : 40,
    },
    /** Rải vào <Legend {...legend} /> */
    legend: {
      wrapperStyle: { fontSize: isMobile ? 11 : 12 },
    },
  };
}
