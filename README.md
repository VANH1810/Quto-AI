<div align="center">

# 🛡️ BẢN TIN AN TOÀN

### Hệ thống cảnh báo sớm thiên tai & cứu hộ cấp xã — Điện Biên

*AI-native, multi-channel, multilingual disaster early-warning & rescue-coordination platform.*

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Web-Next.js%2015-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/AI-LangGraph%20%2B%20Celery-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![Supabase](https://img.shields.io/badge/DB-Supabase%20Postgres-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Tổng quan

Điện Biên là vùng núi cao, thời tiết khắc nghiệt và thay đổi nhanh: **lũ quét, sạt lở, mưa
lớn, rét hại, sương mù**. Thông tin dự báo hiện chỉ ở cấp tỉnh — người dân **thôn/bản nhận
muộn, không đủ chi tiết theo từng vùng, và khó hiểu** với người ít đọc chữ.

**BẢN TIN AN TOÀN** giải quyết bài toán *đưa thông tin đúng người — đúng lúc — đúng ngôn ngữ*:

- **Dự báo chi tiết cấp xã** — hạ quy mô dữ liệu thời tiết về từng xã (điểm + độ cao).
- **Cảnh báo tự động kèm hành động cụ thể** — AI soạn bản tin đa ngữ khi vượt ngưỡng QĐ18/2021.
- **Đa kênh & đa ngữ** — Zalo · SMS · loa truyền thanh IP; Tiếng Việt · Thái · Mông.
- **Giao diện trực quan** — biểu tượng, màu sắc, thang cảnh báo thay cho thuật ngữ khí tượng.
- **Cứu hộ (SOS)** — người dân ghim vị trí nguy hiểm → điều phối đội cứu hộ gần nhất (kiểu app bão Yagi).

> **Nguyên tắc cốt lõi:** mức độ nguy hiểm do **luật cứng QĐ18/2021** quyết định (minh bạch,
> kiểm toán được) — **AI chỉ soạn/dịch bản tin**, không tự quyết cấp độ. An toàn & dễ giải trình.

---

## ✨ Tính năng chính

| | Tính năng |
|---|---|
| 🌦️ | Dự báo **7 ngày cho 45 xã/phường** Điện Biên (Open-Meteo, hiệu chỉnh độ cao + bias-correction) |
| ⚖️ | **Risk engine tất định** theo QĐ18/2021/QĐ-TTg — thang rủi ro 5 cấp (xanh→tím) |
| 🤖 | **AI agent (LangGraph)** soạn bản tin đa ngữ Việt/Thái/Mông + gợi ý hành động |
| 🧑‍⚖️ | **Human-in-the-loop** — cảnh báo cấp cao (≥ cam) phải cán bộ duyệt mới gửi |
| 📡 | Gửi **đa kênh**: Zalo ZNS · SMS brandname · loa truyền thanh IP (ngắt lịch khẩn) |
| 🔊 | **TTS tiếng dân tộc** (Meta MMS: Thái `blt`, Mông `mww`) đọc bản tin ra loa |
| 🆘 | **Cứu hộ SOS** — dân gửi toạ độ → dashboard điều phối → cử đội gần nhất (km + ETA) |
| 🗺️ | **Bản đồ nguy cơ** realtime (Leaflet) + nơi trú ẩn an toàn gần nhất |
| 📜 | **Nhật ký gửi tin** + audit từng bước (data provenance) |
| 🔐 | Đăng nhập JWT phân quyền **theo từng xã**; đa nguồn dữ liệu có trích dẫn |

---

## 🏗️ Kiến trúc

```
                          ┌────────────────────────────┐
                          │      FRONTEND (Vercel)      │  Next.js 15 · React 19 · Leaflet
                          │  Dashboard + Bản đồ + SOS   │
                          └───────────┬────────────────┘
                                      │ HTTPS / Supabase Realtime
             ┌────────────────────────┼─────────────────────────┐
             ▼                        ▼                          ▼
   ┌──────────────────┐   ┌───────────────────────┐   ┌────────────────────┐
   │ BACKEND (Render) │   │  AI AGENT (VPS/Docker) │   │  DATA PIPELINE     │
   │ FastAPI · JWT    │   │  agent_worker :8100    │   │  (cron / worker)   │
   │ 12 nhóm API      │◄─►│  LangGraph + Celery    │   │  Fetch 7 ngày →    │
   │ control-plane    │   │  agent · dispatch      │   │  point extract →   │
   └────────┬─────────┘   └──────────┬────────────┘   │  bias-correction   │
            │                        │                 └─────────┬──────────┘
            │        ┌───────────────┴────────────┐             │
            ▼        ▼                             ▼             ▼
   ┌─────────────────────┐        ┌───────────────────────────────────┐
   │ Supabase (Postgres) │        │ RabbitMQ (broker) · Redis (result) │
   │ 11 bảng dữ liệu     │        └───────────────────────────────────┘
   └─────────────────────┘
            ▲
   ┌────────┴────────────────────────────────────────────────────────────┐
   │ Nguồn: Open-Meteo · GeoNames · Copernicus GLO-90 · QĐ18/2021/QĐ-TTg  │
   └─────────────────────────────────────────────────────────────────────┘
```

**Luồng chính:** `Dự báo → Risk engine (QĐ18) → AI soạn bản tin đa ngữ → Human duyệt (nếu cấp cao)
→ Gửi đa kênh → Nhật ký + provenance`. Song song: `Dân gửi SOS → điều phối cứu hộ`.

---

## 📁 Cấu trúc kho mã

```
quto-ai/
├── frontend/        # Next.js 15 + React 19 + Leaflet — dashboard, bản đồ, SOS (Vercel)
├── backend/         # FastAPI control-plane — 12 nhóm API, JWT, Supabase (Render)
├── agent_worker/    # AI: LangGraph + Celery + FastAPI(:8100) + RabbitMQ/Redis/Postgres (Docker)
├── data-pipeline/   # Fetch Open-Meteo 7 ngày → point extract → bias correction
├── config/          # cấu hình dùng chung
├── tests/           # kiểm thử tích hợp E2E
└── README.md
```

| Thành phần | Công nghệ | Vai trò | Triển khai |
|---|---|---|---|
| **frontend** | Next.js 15, React 19, Leaflet, TypeScript, Tailwind | Dashboard cán bộ + bản đồ dân | Vercel |
| **backend** | FastAPI, Pydantic v2, JWT, Supabase | Control-plane: dữ liệu, cảnh báo, cứu hộ, loa, nhật ký | Render |
| **agent_worker** | LangGraph, Celery, FastAPI, RabbitMQ, Redis | AI soạn bản tin + gửi đa kênh (bất đồng bộ) | VPS / Railway (Docker) |
| **data-pipeline** | httpx, Open-Meteo | Hạ quy mô dự báo 7 ngày + hiệu chỉnh sai số | Cron / worker |

---

## 🚀 Bắt đầu nhanh

> Yêu cầu: **Python ≥ 3.12**, **Node ≥ 18**, (tuỳ chọn) **Docker**.

<details open>
<summary><b>1) Backend (API control-plane)</b></summary>

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # → http://localhost:8000/docs
```
Khởi động tự seed **45 xã + 45 cán bộ + 450 công dân + đội cứu hộ**.
Đăng nhập: `canbo.<mã_xã>@dienbien.gov.vn` / `123456` (vd `canbo.muong_pon@…`).
Chi tiết: [backend/README.md](backend/README.md).
</details>

<details>
<summary><b>2) AI Agent (agent_worker)</b></summary>

```bash
cd agent_worker
docker compose up --build            # rabbitmq · redis · postgres · agent-api:8100 · 2 worker
# Swagger AI: http://localhost:8100/docs   ·   RabbitMQ UI: http://localhost:15672 (guest/guest)
```
AI thật: đặt `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` trong `.env` (mặc định `mock`).
API: [agent_worker/ENDPOINTS.md](agent_worker/ENDPOINTS.md).
</details>

<details>
<summary><b>3) Data pipeline (dự báo 7 ngày)</b></summary>

```bash
cd data-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline.run               # 1 lần  ·  --loop cho hourly tick
# → output/forecast_<xã>.json + output/latest.json
```
Nguồn & độ tin cậy: [data-pipeline/SOURCES.md](data-pipeline/SOURCES.md).
</details>

<details>
<summary><b>4) Frontend (dashboard + bản đồ)</b></summary>

```bash
cd frontend
npm install
npm run dev                          # → http://localhost:3000
```
Đặt `NEXT_PUBLIC_API_URL` (backend) + Supabase keys trong `.env.local`.
</details>

---

## ⚙️ Cấu hình (biến môi trường chính)

| Biến | Thành phần | Ý nghĩa |
|---|---|---|
| `DB_BACKEND` | backend | `memory` (chạy ngay) \| `supabase` (Postgres) |
| `SUPABASE_URL` / `SUPABASE_KEY` | backend, agent | Kết nối Supabase (service_role) |
| `LLM_PROVIDER` | backend, agent | `mock` \| `openai` \| `gemini` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | agent | Khoá LLM để AI chạy thật |
| `RABBITMQ_URL` / `REDIS_URL` | backend↔agent | Hàng đợi + kết quả (Celery) |
| `HUMAN_APPROVAL_MIN_LEVEL` | backend, agent | Cấp ≥ giá trị này phải cán bộ duyệt (mặc định 3) |
| `JWT_SECRET` | backend | Ký token đăng nhập |
| `CORS_ORIGINS` | backend | Domain FE được phép gọi |

---

## ☁️ Triển khai (production)

| Lớp | Khuyến nghị | Ghi chú |
|---|---|---|
| **Frontend** | Vercel | `next build`; đặt `NEXT_PUBLIC_API_URL` |
| **Backend** | Render (Web Service) | Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **AI Agent** | **VPS + `docker compose up -d`** | Đúng như thiết kế; Caddy HTTPS cho `:8100`; RabbitMQ/Redis chạy nội bộ |
| **Database** | Supabase | Chạy `backend/db/schema.sql` (11 bảng) |
| **Broker** *(nếu backend↔agent qua Celery)* | CloudAMQP + Upstash Redis | Managed free; **không dùng ngrok** cho broker |

> Lựa chọn managed cho AI: **Railway / Fly.io** chạy 3 process Docker + CloudAMQP + Upstash + Supabase.

---

## 🔌 API (tóm tắt)

**Backend** (`:8000/docs`) — 12 nhóm: Tài khoản · Bản đồ&Dự báo · Công dân (DB1) · Cán bộ (DB2)
· Cảnh báo (AI) · Demo · Nơi trú ẩn · Tin nhắn cá nhân (DB3) · Cứu hộ SOS · **Loa truyền thanh**
· **Nhật ký gửi tin** · Hệ thống. Xem [backend/README.md](backend/README.md).

**AI Agent** (`:8100/docs`) — `POST /warnings` (tạo cảnh báo, AI chạy ngay) · `/approve` · `/reject`
· `/seed` · tra cứu dữ liệu. Xem [agent_worker/ENDPOINTS.md](agent_worker/ENDPOINTS.md).

---

## 📊 Nguồn dữ liệu & tính minh bạch

Hệ thống ghi rõ **cái gì là thật / cái gì là ước lượng** trong mọi phản hồi:

| Dữ liệu | Nguồn | Trạng thái |
|---|---|---|
| Dự báo thời tiết (45 xã) | **Open-Meteo** (ECMWF/ICON/GFS) — CC BY 4.0 | ✅ Thật |
| Hạ quy mô theo độ cao | **Copernicus GLO-90 DEM** | ✅ Thật |
| Toạ độ xã | **GeoNames** (qua Open-Meteo Geocoding) — CC BY 4.0 | 🟡 Gắn nhãn độ tin cậy từng xã |
| Ngưỡng rủi ro | **Quyết định 18/2021/QĐ-TTg** | ✅ Pháp lý |
| Bias correction | Quantile mapping / hiệu chỉnh theo độ cao | 🟡 Chờ dữ liệu **trạm KTTV Điện Biên** |
| Dân cư / cán bộ / trú ẩn | Sinh mẫu (seed) | ⚠️ Mock (thay bằng CSDL thật) |

Chi tiết: [data-pipeline/SOURCES.md](data-pipeline/SOURCES.md).

---

## 🗺️ Lộ trình

- [ ] Hiệu chỉnh bias bằng **dữ liệu trạm KTTV Điện Biên** (thay số ước lượng).
- [ ] **Ranh giới hành chính chính thức 2025** cho 45 xã (thay toạ độ xấp xỉ).
- [ ] Nowcasting 0–6h (mô hình XGBoost/LSTM) + **IMERG** (mưa vệ tinh).
- [ ] Cắm **Zalo OA/ZNS + SMS brandname + loa IP** thật (đang mock).
- [ ] Fine-tune **TTS tiếng dân tộc** + audio cộng đồng thu sẵn.
- [ ] Xuất **CAP-XML** (chuẩn cảnh báo quốc tế) để liên thông.

---

## 🧩 Tech stack

**Backend:** FastAPI · Pydantic v2 · PyJWT · httpx · Supabase
**AI:** LangGraph · Celery · RabbitMQ · Redis · Meta MMS TTS
**Frontend:** Next.js 15 · React 19 · TypeScript · Leaflet · Tailwind
**Data/ML:** Open-Meteo · Copernicus GLO-90 · GeoNames · TensorFlow (nowcasting)
**Hạ tầng:** Docker · Render · Vercel · Supabase

---

## ⚖️ Tuân thủ

- **Luật An ninh mạng 2018 + NĐ53/2022** — dữ liệu host tại Việt Nam.
- **NĐ13/2023/NĐ-CP** — bảo vệ dữ liệu cá nhân (SĐT/địa chỉ): cần đồng ý (consent) cho
  Zalo/SMS; Điều 13 cho phép xử lý khẩn cấp để bảo vệ tính mạng.

---

## 📄 Giấy phép

[MIT License](LICENSE) © 2026 Quoc-Viet-Anh Tran.

> **Miễn trừ:** Đây là hệ thống hỗ trợ ra quyết định. Quyết định cảnh báo/sơ tán cuối cùng
> thuộc về cơ quan phòng chống thiên tai có thẩm quyền. Dữ liệu dân cư/cán bộ trong demo là
> dữ liệu mẫu, không phải thông tin cá nhân thật.
