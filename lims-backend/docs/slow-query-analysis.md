# Phân tích truy vấn chậm (R6.3)

## Cấu hình đã bật

`docker-compose.prod.yml` — khối `command` của postgres:

| Tham số | Giá trị | Mục đích |
|---|---|---|
| `log_min_duration_statement` | `500ms` | Ghi log mọi câu chạy quá 500ms |
| `shared_preload_libraries` | `pg_stat_statements` | Thống kê tích luỹ theo câu truy vấn |
| `pg_stat_statements.max` | `5000` | Số câu theo dõi |
| `pg_stat_statements.track` | `top` | Chỉ câu ở tầng ngoài cùng, không đếm câu lồng |

> `shared_preload_libraries` **phải nạp lúc khởi động** — `CREATE EXTENSION` sau
> đó không đủ. Đổi giá trị này cần restart Postgres.

## Truy vấn 20 câu tốn thời gian nhất

```sql
SELECT calls,
       round(mean_exec_time::numeric, 1)  AS ms_trung_binh,
       round(total_exec_time::numeric)    AS ms_tong,
       rows,
       query
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 20;
```

Đặt lại bộ đếm trước mỗi đợt đo:

```sql
SELECT pg_stat_statements_reset();
```

## Xem log câu chậm

```bash
docker compose -f docker-compose.prod.yml logs postgres | grep "duration:"
```

## Cách đọc

| Dấu hiệu | Nghĩa là | Xử lý |
|---|---|---|
| `calls` rất cao, `mean_exec_time` thấp | Có thể là N+1 | Kiểm serializer, nạp gộp (xem R6.2) |
| `mean_exec_time` cao, `calls` thấp | Thiếu index hoặc quét bảng | `EXPLAIN (ANALYZE, BUFFERS)` |
| `rows` >> số dòng hiển thị | Nạp thừa rồi cắt ở client | Chuyển sang phân trang server (R5.4) |

## Ghi nhận lần chạy đầu

Chưa có dữ liệu production. Chạy lại mục "20 câu tốn nhất" sau **một tuần** vận
hành thật rồi dán kết quả vào đây — số liệu trên môi trường dev với 614 dòng
`test_parameters` và 96 user không đại diện cho tải thật.
