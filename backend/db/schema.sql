-- BẢN TIN AN TOÀN — Schema Supabase (Postgres)
-- Chạy trong Supabase → SQL Editor. Bật PostGIS nếu muốn truy vấn không gian.
-- create extension if not exists postgis;

-- 1) Xã / cụm dân cư (bản đồ)
create table if not exists communes (
  code                     text primary key,
  name                     text not null,
  district                 text,
  lat                      double precision,
  lon                      double precision,
  elevation_m              double precision,
  landslide_susceptibility text default 'medium',
  population               integer default 0
);

-- 2) DB1 — Công dân (khoá = CCCD)
create table if not exists citizens (
  cccd              text primary key,
  id                text,
  full_name         text not null,
  age               integer,
  address           text,
  phone             text,
  ethnicity         text,
  religion          text,
  commune_code      text references communes(code),
  lat               double precision,
  lon               double precision,
  consent_zalo_sms  boolean default true,
  preferred_lang    text default 'vi'
);
create index if not exists idx_citizens_commune on citizens(commune_code);

-- 3) DB2 — Admin / cán bộ
create table if not exists admins (
  id            text primary key,
  email         text unique not null,
  full_name     text not null,
  age           integer,
  phone         text,
  ethnicity     text,
  religion      text,
  role          text default 'commune',
  communes      text[] default '{}',
  password_hash text not null
);

-- 4) Nơi trú ẩn an toàn
create table if not exists shelters (
  id            text primary key,
  commune_code  text references communes(code),
  name          text not null,
  address       text,
  lat           double precision,
  lon           double precision,
  capacity      integer default 0,
  kind          text default 'community_hall',
  contact_phone text
);
create index if not exists idx_shelters_commune on shelters(commune_code);

-- 5) Cảnh báo (bản tin cấp xã)
create table if not exists alerts (
  id           text primary key,
  hazard       text,
  commune_code text references communes(code),
  risk_level   integer,
  risk_label   text,
  status       text,
  bulletins    jsonb,
  provenance   jsonb,
  created_at   timestamptz default now(),
  approved_by  text
);

-- 6) DB3 — Tin nhắn cảnh báo tới TỪNG người dân (kèm nơi trú ẩn gần nhất)
-- FK để dạng 'lỏng' (text thường) để mirror từng tin không phụ thuộc thứ tự đẩy.
create table if not exists notifications (
  id                       text primary key,
  alert_id                 text,
  cccd                     text,
  full_name                text,
  address                  text,
  commune_code             text,
  channel                  text,
  lang                     text,
  status                   text,            -- sent | failed | home_visit
  nearest_shelter_id       text,
  nearest_shelter_name     text,
  nearest_shelter_address  text,
  nearest_shelter_km       double precision,
  detail                   text,
  created_at               timestamptz default now()
);
create index if not exists idx_notif_alert on notifications(alert_id);
create index if not exists idx_notif_cccd  on notifications(cccd);

-- 8) Đội cứu hộ
create table if not exists rescue_teams (
  id                 text primary key,
  name               text not null,
  commune_code       text,
  base_lat           double precision,
  base_lon           double precision,
  phone              text,
  capacity           integer default 6,
  status             text default 'available',  -- available | busy
  current_request_id text
);

-- 9) Tin cứu hộ SOS (dân gửi vị trí nguy hiểm)
create table if not exists rescue_requests (
  id                   text primary key,
  lat                  double precision,
  lon                  double precision,
  danger_type          text,   -- flood_trapped | landslide_buried | injured | isolated | missing | other
  num_people           integer default 1,
  full_name            text,
  phone                text,
  cccd                 text,
  note                 text,
  commune_code         text,
  commune_name         text,
  priority             text,   -- critical | high | medium
  status               text,   -- pending | acknowledged | dispatched | resolved | cancelled
  assigned_team_id     text,
  assigned_team_name   text,
  distance_km          double precision,
  eta_min              integer,
  nearest_shelter_name text,
  created_at           text,
  updated_at           text
);
create index if not exists idx_rescue_status on rescue_requests(status);
create index if not exists idx_rescue_commune on rescue_requests(commune_code);


-- Gợi ý bảo mật: bật RLS + policy phù hợp trước khi lên production.
-- alter table citizens enable row level security; (rồi tạo policy theo vai trò)
