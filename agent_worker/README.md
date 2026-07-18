# agent_worker — AI Agent Service (LangGraph + Celery)

Service AI riêng cho hệ cảnh báo thiên tai Điện Biên: nhận **task** từ BackEnd Services
qua **Celery (broker RabbitMQ)**, chạy graph LangGraph gọi tool (Risk Engine / User API /
Shelter / Recommend / Zalo), lưu vết LLM (tool call / response / thinking) vào Postgres,
dùng **Redis làm result backend** cho polling metadata, và gửi đa kênh đa ngữ.

## Kiến trúc (Celery + RabbitMQ + Redis + Postgres)

```
BackEnd Services → FastAPI (api) ──send_task──► RabbitMQ (broker) ──► agent-worker (Celery -Q agent)
        ▲ poll AsyncResult(job_id)                                        │ chạy LangGraph (LLM compose)
        └──────── Redis (result backend) ◄── state/metadata ──────────────┘ enqueue dispatch tasks
                                                                            ▼
                                          RabbitMQ ──► dispatch-worker (Celery -Q dispatch) → Zalo/SMS/loa
```

- **api** — FastAPI: `send_task` job cho Celery, polling `AsyncResult`, endpoint nội bộ ghi DB3.
- **agent-worker** — `celery ... worker -Q agent`: task `agent.run_job` chạy graph (gồm LLM `compose`), quyết định human-loop; task `agent.resume_job` xử lý duyệt/bác.
- **dispatch-worker** — `celery ... worker -Q dispatch`: task `agent.dispatch_message` gửi 1 bản tin, retry, lỗi hẳn → ghi DB3 failed + task đến-tận-nhà.

Broker = **RabbitMQ** (ack/retry/DLQ tin cậy cho task LLM chạy lâu); result backend =
**Redis** (state + metadata cho polling).

## Chạy (Docker)

```bash
docker compose up --build
#   Swagger : http://localhost:8000/docs
#   RabbitMQ: http://localhost:15672  (guest/guest)
```

## Demo E2E (qua Swagger)

1. `POST /api/v1/dev/seed` → seed dữ liệu + admin `canbo@dienbien.gov.vn / 123456`.
2. `POST /api/v1/auth/login` → token → **Authorize**.
3. `POST /api/v1/dev/scenario/muong-pon-2024` **hoặc** `POST /api/v1/agent/jobs {"commune_code":"muong_pon"}` → nhận `job_id`.
4. `GET /api/v1/agent/jobs/{job_id}` → polling:
   - `run.state` = PENDING → PROGRESS (`info.node` = node đang chạy) → SUCCESS.
   - `run.info.status` = `pending_approval` (cấp cao) kèm bản tin đa ngữ, hoặc `dispatching` (cấp thấp tự gửi).
5. Cấp cao: `POST /api/v1/agent/jobs/{job_id}/approve` → task `resume` fan-out dispatch → `GET /api/v1/notifications?alert_id=` xem tin cá nhân (sent + failed→home-visit).

## Polling metadata (Celery AsyncResult)

```
GET /api/v1/agent/jobs/{job_id}
{
  "status": "running|pending_approval|dispatching|failed|...",
  "run":    {"state": "PROGRESS", "info": {"node": "compose"}},
  "resume": {"state": "SUCCESS",  "info": {"status": "dispatching", "dispatched": 2}}
}
```

## Vết LLM (Postgres)

```sql
SELECT seq, kind, name, status, latency_ms FROM agent_spans WHERE run_id = '<job_id>' ORDER BY seq;
-- kind='tool' : risk_engine / user_api / shelter / recommend (input/output)
-- kind='llm'  : compose (content = response, thinking, tokens)
```

## Cấu hình (biến môi trường)

`RABBITMQ_URL` (broker), `REDIS_URL` (result backend), `DATABASE_URL`, `BACKEND_URL`,
`LLM_PROVIDER` (mock/openai/gemini), `HUMAN_APPROVAL_MIN_LEVEL` (mặc định 3),
`DISPATCH_MAX_RETRY`, `ZALO_PROVIDER` (mock/live) + `ZALO_*`, `SERVICE_ADMIN_EMAIL`.

> Nguyên tắc: risk engine **tất định** (QĐ18/2021) — LLM chỉ diễn đạt/dịch, không quyết cấp độ.
