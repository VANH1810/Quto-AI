-- AI backend DB (agent_worker tự chứa). Idempotent (IF NOT EXISTS).
--
-- 2 nhóm:
--   (A) Dữ liệu nghiệp vụ AI cần: citizens, admins, shelters, notifications, home_visits.
--   (B) Vết LLM: agent_runs (trace) + agent_spans (node/tool/llm).
-- Worker đọc/ghi trực tiếp DB này; agent-api phục vụ seed + tra cứu.

-- (A) DỮ LIỆU ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.citizens (
  cccd             text NOT NULL,
  full_name        text NOT NULL,
  age              integer,
  address          text,
  phone            text,
  ethnicity        text,
  commune_code     text,
  lat              double precision,
  lon              double precision,
  consent_zalo_sms boolean DEFAULT true,
  preferred_lang   text DEFAULT 'vi',
  CONSTRAINT citizens_pkey PRIMARY KEY (cccd)
);

CREATE TABLE IF NOT EXISTS public.admins (
  id         text NOT NULL,
  full_name  text NOT NULL,
  email      text,
  phone      text,
  communes   text[] DEFAULT '{}'::text[],
  CONSTRAINT admins_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.shelters (
  id            text NOT NULL,
  commune_code  text,
  name          text NOT NULL,
  address       text,
  lat           double precision,
  lon           double precision,
  capacity      integer DEFAULT 0,
  kind          text DEFAULT 'community_hall',
  contact_phone text,
  CONSTRAINT shelters_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.notifications (
  id                      text NOT NULL,
  alert_id                text,
  cccd                    text,
  full_name               text,
  address                 text,
  commune_code            text,
  channel                 text,
  lang                    text,
  status                  text,          -- sent | failed | home_visit
  nearest_shelter_id      text,
  nearest_shelter_name    text,
  nearest_shelter_address text,
  nearest_shelter_km      double precision,
  detail                  text,
  created_at              timestamp with time zone DEFAULT now(),
  CONSTRAINT notifications_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.home_visits (
  id                text NOT NULL,
  alert_id          text,
  commune_code      text,
  assigned_admin_id text,
  reason            text,
  status            text DEFAULT 'open',  -- open | done
  created_at        timestamp with time zone DEFAULT now(),
  CONSTRAINT home_visits_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_citizens_commune ON public.citizens(commune_code);
CREATE INDEX IF NOT EXISTS idx_shelters_commune ON public.shelters(commune_code);
CREATE INDEX IF NOT EXISTS idx_notif_alert      ON public.notifications(alert_id);
CREATE INDEX IF NOT EXISTS idx_notif_cccd       ON public.notifications(cccd);

-- (B) VẾT LLM ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.agent_runs (
  id                text NOT NULL,
  alert_id          text,
  commune_code      text,
  trigger           text,
  status            text DEFAULT 'running',
  risk_level        integer,
  langs             text[] DEFAULT '{vi,tai,hmn}'::text[],
  llm_provider      text,
  llm_model         text,
  prompt_tokens     integer DEFAULT 0,
  completion_tokens integer DEFAULT 0,
  total_tokens      integer DEFAULT 0,
  error             text,
  created_at        timestamp with time zone DEFAULT now(),
  updated_at        timestamp with time zone DEFAULT now(),
  finished_at       timestamp with time zone,
  CONSTRAINT agent_runs_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.agent_spans (
  id                text NOT NULL,
  run_id            text NOT NULL,
  parent_span_id    text,
  seq               integer NOT NULL,
  kind              text NOT NULL,          -- node | tool | llm
  name              text NOT NULL,
  status            text DEFAULT 'running',
  input             jsonb,
  output            jsonb,
  content           text,
  thinking          text,
  prompt_tokens     integer,
  completion_tokens integer,
  total_tokens      integer,
  finish_reason     text,
  latency_ms        integer,
  error             text,
  created_at        timestamp with time zone DEFAULT now(),
  CONSTRAINT agent_spans_pkey PRIMARY KEY (id),
  CONSTRAINT agent_spans_run_fkey FOREIGN KEY (run_id) REFERENCES public.agent_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_commune ON public.agent_runs(commune_code);
CREATE INDEX IF NOT EXISTS idx_agent_spans_run    ON public.agent_spans(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_spans_kind   ON public.agent_spans(run_id, kind);
