# Deploy AI service (agent_worker) — FREE & ổn định

`agent_worker` là service AI riêng (LangGraph + Celery). Nó cần **worker chạy nền
liên tục** → **không hợp với Render free** (Celery worker là service *trả phí*, web free
lại ngủ sau 15 phút). Cách **free thật + luôn bật** = 1 **VM free** chạy `docker compose`.

## Vì sao bản prod bỏ RabbitMQ?
Bản prod (`docker-compose.prod.yml`) dùng **Redis làm broker + result backend** (1 hạ tầng).
Ít RAM hơn, ít thành phần hơn → vừa VM free, ổn định hơn. Kiến trúc vẫn là Celery worker
+ human-in-the-loop. (Muốn RabbitMQ lại: đặt `CELERY_BROKER_URL=amqp://...`.)

## Khuyến nghị: Oracle Cloud Always Free (ARM Ampere A1)
Free **vĩnh viễn**, luôn bật, tối đa 4 vCPU / 24 GB — thừa sức chạy cả stack.
(Thay thế: bất kỳ VPS ~5$/tháng, hoặc GCP e2-micro free — RAM 1 GB hơi sát.)

### Các bước
1. Tạo VM Ubuntu 22.04 (Always Free, ARM), mở **Ingress** cổng `8100` (và `80/443` nếu dùng domain).
2. SSH vào VM, cài Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER && newgrp docker
   ```
3. Lấy code + cấu hình:
   ```bash
   git clone <repo-url> quto && cd quto/agent_worker
   cp .env.prod.example .env
   nano .env            # xem phần Data plane bên dưới
   ```
4. Chạy:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml ps        # 5 service Up (redis, postgres, 3 app)
   ```
5. Nạp dữ liệu mẫu + thử:
   ```bash
   curl -X POST http://<IP-VM>:8100/seed
   curl -X POST http://<IP-VM>:8100/warnings \
        -H 'content-type: application/json' \
        -d '{"commune_code":"muong_pon","langs":["vi","tai","hmn"]}'
   ```
   Mở `http://<IP-VM>:8100/docs` để thao tác qua Swagger.

### HTTPS (khi có domain)
Trỏ `ai.tenmien.vn` A-record về IP VM, mở 80/443, rồi:
```bash
DOMAIN=ai.tenmien.vn docker compose -f docker-compose.prod.yml --profile tls up -d --build
# → https://ai.tenmien.vn  (Caddy tự xin cert Let's Encrypt)
```

## Data plane — QUAN TRỌNG (để FE thấy dữ liệu)
`agent_worker` ghi `notifications`/`alerts` vào Postgres của **chính nó**. FE lại đọc
qua **Supabase Realtime**. Muốn FE thấy → trỏ AI vào **cùng Supabase**:

1. Supabase → *Project Settings → Database → Connection string → URI* (Session pooler, cổng 5432).
2. Đổi scheme `postgres://` → `postgresql+asyncpg://`, bỏ `?sslmode=...` nếu có.
3. Dán vào `.env`: `DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<pw>@...pooler.supabase.com:5432/postgres`
4. **Kiểm tra schema khớp:** `agent_worker/db/schema.sql` phải tương thích bảng Supabase
   (`notifications`, `citizens`, `admins`, `shelters`). `init_models()` chạy `CREATE TABLE
   IF NOT EXISTS` lúc boot nên an toàn với bảng đã có; nếu cột lệch thì căn lại 1 lần.

> Không trỏ Supabase = AI vẫn chạy tốt (Postgres nội bộ), nhưng FE phải gọi thẳng
> `GET http://<IP-VM>:8100/notifications` thay vì đọc Supabase.

## Kết nối từ backend (Render) → AI
Backend gọi AI qua **HTTP** (đồng bộ): đặt biến `AGENT_BASE_URL=http://<IP-VM>:8100`
(hoặc `https://ai.tenmien.vn`) trong env của Render. Xem phần wiring ở backend.

## Vận hành
```bash
docker compose -f docker-compose.prod.yml logs -f agent-worker   # xem worker chạy graph
docker compose -f docker-compose.prod.yml restart agent-worker
docker compose -f docker-compose.prod.yml down                   # dừng (giữ volume pgdata)
```
