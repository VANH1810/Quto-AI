# Backend — Dien Bien Weather AI

FastAPI backend (control plane) for the commune-level disaster early-warning system.

- **Swagger UI:** `http://localhost:8000/docs`
- **Health:** `GET /health`
- **Start:** `uvicorn app.main:app --reload`

---

## 1. Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup bootstrap
│   ├── config.py            # Settings from .env (pydantic-settings)
│   ├── security.py          # JWT token creation & verification
│   ├── api/routes/          # 12 API route groups
│   │   ├── auth.py          #   1. Login (token-based)
│   │   ├── forecast.py      #   2. Map & forecast (commune list, 7-day, risk overlay)
│   │   ├── citizens.py      #   3. Citizen database (DB1)
│   │   ├── admins.py        #   4. Official database (DB2)
│   │   ├── alerts.py        #   5. AI-powered warnings (trigger, approve, reject)
│   │   ├── dev.py           #   6. Demo & seed endpoints
│   │   ├── shelters.py      #   7. Safe shelters
│   │   ├── notifications.py #   8. Delivery notifications (DB3)
│   │   ├── rescue.py        #   10. SOS rescue coordination
│   │   ├── loudspeakers.py  #   11. IP loudspeaker management
│   │   ├── interactions.py  #   12. Delivery log & audit trail
│   │   ├── admin_console.py #   Admin console dashboard
│   │   └── admin_sos.py     #   Admin SOS management
│   ├── services/            # Business logic and data storage
│   │   ├── citizens.py      #   CRUD for citizens (in-memory + Supabase mirror)
│   │   ├── admins.py        #   CRUD for officials
│   │   ├── alerts.py        #   Alert lifecycle (trigger, approve, reject)
│   │   ├── seed.py          #   Demo data generator (45 communes, 450 citizens)
│   │   ├── geo_data.py      #   45 communes of Dien Bien with coordinates
│   │   ├── shelters.py      #   Shelter generator (2-3 per commune)
│   │   ├── notifications.py #   Notification storage & queries
│   │   ├── rescue.py        #   SOS request handling
│   │   ├── loudspeakers.py  #   Loudspeaker registry & broadcast
│   │   ├── interactions.py  #   Delivery interaction log
│   │   ├── commune_boundary.py # Commune boundary data
│   │   ├── commune_overview.py # Commune overview aggregation
│   │   ├── admin_scope.py   #   Admin permissions per commune
│   │   └── supabase_repo.py #   Supabase push/fetch (optional)
│   ├── agents/              # Inline AI fallback (deprecated, kept for AGENT_MODE=local)
│   │   ├── orchestrator.py  #   Agent orchestrator
│   │   └── risk_engine.py   #   Local risk evaluation
│   ├── providers/           # External service providers (mockable)
│   │   ├── weather.py       #   Open-Meteo weather client
│   │   ├── llm.py           #   LLM client (mock/openai/gemini)
│   │   ├── tts.py           #   Text-to-speech (mock/MMS)
│   │   ├── dispatch.py      #   Multi-channel dispatcher (mock)
│   │   └── agent_client.py  #   HTTP client to agent_worker (AGENT_MODE=remote)
│   └── schemas/             # Pydantic models for all API groups
├── pipeline/                # Live/scenario pipeline (see Risk Engine docs)
├── nowcast/                 # LSTM nowcast model artifacts & inference
├── fetchers/                # Open-Meteo weather data fetcher
├── downscale/               # Quantile-mapping bias correction
├── db/
│   └── schema.sql           # Supabase schema (11 tables)
├── scripts/                 # Build commune masks, fit quantile maps
├── tests/                   # Backend unit tests
│   ├── test_admin_scope.py
│   ├── test_commune_boundary.py
│   ├── test_commune_overview.py
│   ├── test_cors.py
│   └── test_sos_rate_limit.py
├── Dockerfile               # Render/Docker deployment
├── render.yaml              # Render blueprint
├── Procfile                 # Render start command
├── .env.example             # Environment variable template
└── requirements.txt         # Python dependencies
```

## 2. API Groups (12 total, Swagger `/docs`)

| Tag | Group | Key Endpoints |
|-----|-------|---------------|
| 1 | Auth | `POST /auth/login` → JWT token |
| 2 | Map & Forecast | `GET /communes`, `GET /forecast/{code}`, `GET /risk-map` |
| 3 | Citizens (DB1) | `GET /citizens`, `GET /citizens/{cccd}`, search |
| 4 | Officials (DB2) | `GET /admins`, `GET /admins/{code}` |
| 5 | AI Alerts | `POST /alerts/trigger`, `POST /alerts/{id}/approve`, `/reject`, retry |
| 6 | Demo | `POST /dev/seed`, `POST /dev/scenario/muong-pon-2024`, Supabase push |
| 7 | Shelters | `GET /shelters`, `GET /shelters/nearest` |
| 8 | Notifications (DB3) | `GET /notifications`, `GET /notifications/failed-only`, `PATCH /notifications/{id}` |
| 10 | SOS Rescue | `POST /rescue/sos`, `GET /rescue/requests`, assign |
| 11 | Loudspeakers | `GET /loudspeakers`, `POST /loudspeakers/{id}/broadcast` |
| 12 | Delivery Log | `GET /interactions`, filter by commune/channel/status |
| 9 | System | `GET /health`, `GET /config` |

## 3. Database

The backend supports two storage modes, controlled by `DB_BACKEND`:

- **`memory`** (default): In-memory storage, auto-seeded on startup. No external DB needed.
- **`supabase`**: Supabase Postgres backend. Schema at `backend/db/schema.sql` (11 tables: citizens, admins, alerts, notifications, shelters, rescue_requests, loudspeakers, interactions, admin_sessions, etc.).

### Auto-seed on startup

The `main.py:_bootstrap()` function ensures the system always starts with data:

```python
# From backend/app/main.py (lines 65-87):
# 1. If Supabase is enabled, pull citizens + admins from remote
# 2. If no admins exist, auto-seed 45 officials + 450 citizens
# Login: canbo.<commune_code>@dienbien.gov.vn / 123456
```

## 4. Health Check

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.4.0","db_backend":"memory",
#    "weather_provider":"mock","llm_provider":"mock","human_approval_min_level":3}
```

## 5. Quick Start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Defaults work without changes
uvicorn app.main:app --reload    # → http://localhost:8000/docs
```

Login with `canbo.muong_pon@dienbien.gov.vn` / `123456` then test the Muong Pon scenario at `POST /dev/scenario/muong-pon-2024`.

## 6. Configuration

All settings via `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_BACKEND` | `memory` | Storage backend (`memory` / `supabase`) |
| `LLM_PROVIDER` | `mock` | LLM provider (`mock` / `openai` / `gemini`) |
| `WEATHER_PROVIDER` | `mock` | Weather API (`mock` / `open-meteo`) |
| `DISPATCH_PROVIDER` | `mock` | Dispatch engine (`mock` / `agent_worker`) |
| `AGENT_MODE` | `local` | AI agent mode (`local` / `remote`) |
| `AGENT_BASE_URL` | — | agent_worker URL for remote mode |
| `HUMAN_APPROVAL_MIN_LEVEL` | `3` | Risk level requiring human approval |
| `JWT_SECRET` | — | Token signing key |
| `SUPABASE_URL/KEY` | — | Supabase credentials |
