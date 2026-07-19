# Deployment Guide — Dien Bien Weather AI

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

**Environment variables** (set in Vercel dashboard):

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (e.g., `https://api.onrender.com`) |

## 3. Backend (Render / Docker)

### Render

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
DB_BACKEND=memory
LLM_PROVIDER=mock
WEATHER_PROVIDER=mock
AGENT_MODE=remote
AGENT_BASE_URL=https://agent-worker.onrender.com:8100
HUMAN_APPROVAL_MIN_LEVEL=3
CORS_ORIGINS=https://your-frontend.vercel.app
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
curl -X POST https://your-backend.onrender.com/dev/seed
curl -X POST https://your-backend.onrender.com/dev/supabase/push-seed
```

## 6. Post-Deployment Verification

After deploying each component:

### Backend health check

```bash
curl https://your-backend.onrender.com/health
# Expected: {"status":"ok","version":"0.4.0","db_backend":"memory",...}
```

### AI Worker health check

```bash
curl https://your-agent-worker.onrender.com:8100/health
# Expected: {"status":"ok","broker":"...","backend":"redis"}
```

### End-to-end test

```bash
# 1. Login
TOKEN=$(curl -s -X POST https://your-backend.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"canbo.muong_pon@dienbien.gov.vn","password":"123456"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Trigger Muong Pon scenario
curl -s -X POST https://your-backend.onrender.com/dev/scenario/muong-pon-2024 \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
