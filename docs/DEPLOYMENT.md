# Deployment Guide — Dien Bien Weather AI

---

## 0. Live Deployment (production URLs)

| Component | Live URL | Notes |
|-----------|----------|-------|
| **Frontend** (Vercel) | https://quto-ai-eta.vercel.app | Next.js app |
| **Backend API** (Render) | https://quto-ai.onrender.com | [Swagger](https://quto-ai.onrender.com/docs) · [Health](https://quto-ai.onrender.com/health) |
| **AI Agent Worker** (Render) | https://quto-ai-2.onrender.com | [Swagger](https://quto-ai-2.onrender.com/docs) · [Health](https://quto-ai-2.onrender.com/health) |

> The AI Agent Worker runs on Render **free** as a single web service (FastAPI + Celery
> worker via `honcho`), with **Render Key Value (Redis)** as broker/result backend and
> **Render Postgres** for data. See §4 for the setup.

---

## 1. Prerequisites

| Component | Requirement |
|-----------|-------------|
| Frontend | Node.js 20+, npm |
| Backend | Python 3.11+, pip |
| AI Worker | Docker, Docker Compose |
| Production DB | Supabase account (free tier) |

## 2. Frontend (Vercel)

The frontend is configured for Vercel deployment via `frontend/vercel.json`.

### Local build verification

```bash
cd frontend
npm install
npm run lint           # ESLint
npm run typecheck      # TypeScript type checking
npm run build          # Production build
```

### Deploy to Vercel

```bash
# Using Vercel CLI
npx vercel --prod

# Or connect GitHub repo to Vercel dashboard with:
# - Framework Preset: Next.js
# - Build Command: npm run build
# - Output Directory: .next
```

**Live:** https://quto-ai-eta.vercel.app

**Environment variables** (set in Vercel dashboard):

| Variable | Value |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://quto-ai.onrender.com` (live backend) |
| `APP_BACKEND_URL` | `https://quto-ai.onrender.com` |

## 3. Backend (Render / Docker) 

### Render

**Live:** https://quto-ai.onrender.com ([Swagger](https://quto-ai.onrender.com/docs))

The backend has a `render.yaml` blueprint for Render Blueprint deployment:

```yaml
# backend/render.yaml — auto-deploy via Render Blueprint
services:
  - type: web
    name: dienbien-weather-ai-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Or manual setup:**
1. Create a new **Web Service** on Render.
2. Set **Build Command**: `pip install -r requirements.txt`
3. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Environment variables:**

```
DB_BACKEND=supabase
LLM_PROVIDER=mock
WEATHER_PROVIDER=openmeteo
AGENT_MODE=remote
AGENT_BASE_URL=https://quto-ai-2.onrender.com
HUMAN_APPROVAL_MIN_LEVEL=3
CORS_ORIGINS=https://quto-ai-eta.vercel.app
JWT_SECRET=<random-secret>
```

### Docker

```bash
cd backend
docker build -t dienbien-backend .
docker run -p 8000:8000 dienbien-backend
```

## 4. AI Agent Worker (Docker Compose)

### Development stack

```bash
cd agent_worker
docker compose up --build
# Starts: RabbitMQ, Redis, Postgres, agent-api, agent-worker, dispatch-worker
```

### Production stack (Redis-only, no RabbitMQ)

The production stack at `agent_worker/docker-compose.prod.yml` uses Redis as both broker and result backend (reducing resource usage):

```bash
cd agent_worker
cp .env.example .env
# Edit .env for production
docker compose -f docker-compose.prod.yml up -d
```

### Environment variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://quto:quto@localhost:5432/quto` |
| `CELERY_BROKER_URL` | Message broker URL | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Result backend URL | `redis://localhost:6379/0` |
| `TELEGRAM_PROVIDER` | Telegram mode | `mock` or `live` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | — |
| `LLM_API_KEY` | OpenAI/FPT API key | — |
| `LLM_BASE_URL` | LLM API base URL | `https://api.fpt.ai/v1` |
| `HUMAN_APPROVAL_MIN_LEVEL` | Risk level requiring approval | `3` |
| `DISPATCH_MAX_RETRY` | Max retries per message | `3` |

## 5. Database (Supabase)

### Schema

```bash
# Open Supabase SQL Editor and paste:
backend/db/schema.sql
```

This creates 11 tables: citizens, admins, alerts, notifications, shelters, rescue_requests, loudspeakers, interactions, admin_sessions, commune_boundaries, commune_overview_cache.

### Seed data

```bash
# Via backend API
curl -X POST https://quto-ai.onrender.com/dev/seed
curl -X POST https://quto-ai.onrender.com/dev/supabase/push-seed
```

## 6. Post-Deployment Verification

After deploying each component:

### Backend health check

```bash
curl https://quto-ai.onrender.com/health
# Expected: {"status":"ok","version":"0.4.0","db_backend":"memory",...}
```

### AI Worker health check

```bash
curl https://quto-ai-2.onrender.com/health
# Expected: {"status":"ok","broker":"...","backend":"redis"}
```

### End-to-end test

```bash
# 1. Login
Truy cập vào link dưới rồi vào login đăng nhập tài khoản Admin
TOKEN=$(curl -s -X POST https://quto-ai.onrender.com \
  -H "Content-Type: application/json" \
  -d '{"email":"canbo.muong_pon@dienbien.gov.vn","password":"123456"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Trigger Muong Pon scenario
Truy cập vào link dưới và tìm /dev/scenario/muong-pon-2024 link này để test
curl -s -X POST https://quto-ai.onrender.com \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
