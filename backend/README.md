# BẢN TIN AN TOÀN — Backend

Hệ **cảnh báo sớm thiên tai + cứu hộ** cấp xã cho **Điện Biên**.
Backend viết bằng **FastAPI (Python)**, có sẵn Swagger UI để test.

> TL;DR: dự báo thời tiết → chấm rủi ro theo **QĐ18/2021** → AI sinh bản tin đa ngữ
> (Việt / Thái / Mông) → gửi Zalo/SMS/loa → và nhận **SOS cứu hộ** từ dân, điều đội
> cứu hộ gần nhất. Mặc định chạy **không cần API key**.

---

## 1. Chạy trong 1 phút

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # tuỳ chọn — mặc định đã chạy được
uvicorn app.main:app --reload # → http://localhost:8000/docs
```

Mở **http://localhost:8000/docs** là thấy toàn bộ API (Swagger).
Khi khởi động, backend **tự tạo sẵn 45 xã + 45 cán bộ + 450 công dân + đội cứu hộ**,
nên đăng nhập được ngay, không cần bước seed thủ công.

---

## 2. Đăng nhập (quan trọng — đọc kỹ)

Chỉ **cán bộ (admin)** mới đăng nhập; người dân thì không.

1. Trên Swagger mở **`1.1 POST /auth/login`** → **Try it out** → nhập:
   ```json
   { "email": "canbo.muong_pon@dienbien.gov.vn", "password": "123456" }
   ```
   → **Execute** → copy chuỗi `access_token` trong kết quả.
2. Bấm nút **Authorize** 🔓 (góc trên phải) → dán token vào ô **Value** → **Authorize** → Close.
3. Xong. Giờ mọi API có ổ khoá 🔒 đều gọi được (thử `1.2 GET /auth/me`).

**Tài khoản** theo mẫu: `canbo.<mã_xã>@dienbien.gov.vn` / `123456`
(mã xã lấy ở `GET /communes`, ví dụ `canbo.tua_chua@…`, `canbo.dien_bien_phu@…`).

> Không có API tự đăng ký — cán bộ được cấp sẵn (seed / trong CSDL).

---

## 3. Kiến trúc tổng quan

```
        Open-Meteo (dự báo, tự hạ quy mô theo độ cao)
                        │
                        ▼
   RISK ENGINE (agents/risk_engine.py)  ← ngưỡng QĐ18/2021, TẤT ĐỊNH, không dùng AI
                        │  (phát hiện lũ quét / mưa lớn / rét hại / sạt lở …)
                        ▼
   AGENT ĐIỀU PHỐI (agents/orchestrator.py)
     • LLM sinh bản tin đa ngữ (chỉ diễn đạt/dịch, KHÔNG quyết cấp độ)
     • TTS đọc loa tiếng dân tộc
     • human-in-the-loop khi cấp cao (≥ cam)
     • ghi nhật ký từng bước (provenance)
                        │
                        ▼
   GỬI ĐA KÊNH: Zalo ZNS · SMS · Loa IP    →  DB3 tin nhắn từng người dân
     lỗi → gửi lại / cán bộ đến tận nhà

   ────────────────────────────────────────────────────────────
   CỨU HỘ (SOS): dân gửi toạ độ nguy hiểm → dashboard admin → cử đội cứu hộ gần nhất
```

**Nguyên tắc cốt lõi:** quyết định mức độ nguy hiểm là **luật cứng (QĐ18)**, minh bạch và
kiểm toán được — **AI chỉ lo phần chữ nghĩa** (viết/dịch bản tin). An toàn + dễ giải trình.

### Công nghệ
| Thành phần | Dùng gì |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Kiểu dữ liệu / validate | Pydantic v2 |
| Thời tiết | Open-Meteo (miễn phí, không key) — tự fallback dữ liệu offline |
| LLM (sinh bản tin) | mock / OpenAI / Gemini / local (đổi ở `.env`) |
| TTS (loa) | mock / Meta MMS (Thái=`blt`, Mông=`mww`) |
| Đăng nhập | JWT (HS256), HTTP Bearer |
| Lưu trữ | In-memory (mặc định) **hoặc** Supabase (Postgres) |

---

## 4. Cơ sở dữ liệu (9 bảng)

Mặc định dữ liệu nằm trong bộ nhớ (in-memory). Khi bật Supabase thì lưu vào Postgres
theo `db/schema.sql`.

| Bảng | Ý nghĩa | Khoá chính |
|---|---|---|
| `communes` | 45 xã/phường + toạ độ, độ cao, độ nhạy cảm sạt lở | `code` |
| `citizens` | **DB1** — công dân (dữ liệu dân cư) | `cccd` |
| `admins` | **DB2** — cán bộ, mỗi xã 1 người | `id` |
| `shelters` | Nơi trú ẩn an toàn theo xã | `id` |
| `alerts` | Cảnh báo (bản tin đa ngữ + nhật ký) | `id` |
| `notifications` | **DB3** — tin nhắn gửi tới TỪNG người dân + nơi trú ẩn gần nhất | `id` |
| `rescue_requests` | Tin **SOS** cứu hộ (toạ độ người gặp nạn) | `id` |
| `rescue_teams` | Đội cứu hộ (mỗi xã 1 đội) | `id` |

Quan hệ chính: `communes` là bảng gốc — `citizens`, `shelters`, `alerts`, `rescue_*`
đều gắn với `commune_code`. `notifications` tham chiếu mềm tới `alerts` + `citizens` +
`shelters`.

---

## 5. Danh sách API (theo nhóm trên Swagger)

### 1 · Tài khoản (admin)
| Method | Path | Việc |
|---|---|---|
| POST | `/api/v1/auth/login` | Đăng nhập, lấy token |
| GET | `/api/v1/auth/me` | Thông tin cán bộ đang đăng nhập |

### 2 · Bản đồ & Dự báo
| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/communes` | 45 xã + toạ độ (vẽ marker) |
| GET | `/api/v1/forecast/{code}` | Dự báo 3–7 ngày cho 1 xã |
| GET | `/api/v1/risk-map` | Cấp độ + màu nguy cơ mọi xã (tô bản đồ) |

### 3 · DB1 · Công dân *(cần đăng nhập)*
| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/citizens` | Danh sách (lọc `?commune_code=`) |
| POST | `/api/v1/citizens` | Thêm/cập nhật (khoá = CCCD) |
| GET | `/api/v1/citizens/{cccd}` | Xem 1 công dân |

### 4 · DB2 · Cán bộ *(cần đăng nhập)*
| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/admins` | Danh sách cán bộ (lọc `?commune_code=`) |

### 5 · Cảnh báo (AI Agent) *(cần đăng nhập)*
| Method | Path | Việc |
|---|---|---|
| POST | `/api/v1/alerts/scan/{code}` | Quét nguy cơ 1 xã → agent tạo cảnh báo |
| GET | `/api/v1/alerts` | Danh sách cảnh báo |
| GET | `/api/v1/alerts/{id}` | Chi tiết + nhật ký |
| POST | `/api/v1/alerts/{id}/approve` | Duyệt & gửi (hoặc bác bỏ) |
| POST | `/api/v1/alerts/{id}/retry` | Gửi lại kênh bị lỗi |

### 6 · Demo
| Method | Path | Việc |
|---|---|---|
| POST | `/api/v1/dev/seed` | Tạo 45 xã + cán bộ + công dân (`?per_commune=`) |
| POST | `/api/v1/dev/scenario/muong-pon-2024` | Tái hiện lũ quét Mường Pồn 25/7 → cấp 3 |
| POST | `/api/v1/dev/supabase/push-seed` | Đẩy toàn bộ dữ liệu lên Supabase |

### 7 · Nơi trú ẩn
| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/shelters` | Danh sách (lọc `?commune_code=`) |
| GET | `/api/v1/shelters/nearest` | Điểm gần nhất theo `lat,lon` |
| POST | `/api/v1/shelters` | Thêm điểm trú ẩn *(cần đăng nhập)* |

### 8 · DB3 · Tin nhắn cá nhân *(cần đăng nhập)*
| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/notifications` | Tin đã gửi (`?alert_id=&cccd=&failed_only=`) |
| PATCH | `/api/v1/notifications/{id}` | Cập nhật trạng thái (vd đã đến tận nhà) |

### 10 · Cứu hộ (SOS)
| Method | Path | Ai dùng | Việc |
|---|---|---|---|
| POST | `/api/v1/rescue/sos` | **Dân (công khai)** | Gửi vị trí nguy hiểm |
| GET | `/api/v1/rescue/requests` | Admin | Dashboard SOS (sắp theo ưu tiên) |
| GET | `/api/v1/rescue/map` | Admin | SOS + đội cứu hộ cho bản đồ |
| GET | `/api/v1/rescue/requests/{id}` | Admin | Chi tiết 1 SOS |
| POST | `/api/v1/rescue/requests/{id}/assign` | Admin | Cử đội gần nhất (km + ETA) |
| PATCH | `/api/v1/rescue/requests/{id}` | Admin | Cập nhật trạng thái |
| GET/POST | `/api/v1/rescue/teams` | Admin | Xem/thêm đội cứu hộ |

### 9 · Hệ thống
| GET | `/health` | Kiểm tra sống + xem cấu hình |

---

## 6. Hai luồng chính (để demo)

### A. Cảnh báo thiên tai
```
6.1 seed → 1.1 login → 6.2 scenario Mường Pồn
→ 5.2 xem cảnh báo (lũ quét CẤP 3, đang "chờ phê duyệt")
→ 5.4 duyệt & gửi  (Zalo/SMS ok, loa lỗi)
→ 8.1 notifications?failed_only=true  (ai chưa nhận)
→ 5.5 gửi lại  /  8.2 cập nhật "đã đến tận nhà"
```

### B. Cứu hộ SOS (kiểu app bản đồ bão Yagi)
```
10.1 /rescue/sos  (dân gửi toạ độ — KHÔNG cần đăng nhập)
   → BE tự suy ra xã + gắn nơi trú ẩn gần nhất + tính mức ưu tiên
10.2 /rescue/requests  (admin thấy trên dashboard, sắp theo ưu tiên)
10.5 /rescue/requests/{id}/assign  (BE cử đội cứu hộ RẢNH gần nhất → km + ETA)
10.6 PATCH status=resolved  (cứu xong → đội rảnh lại)
```

Ví dụ body SOS tối thiểu (bỏ hết các ô `"string"` Swagger tự điền):
```json
{ "lat": 21.531, "lon": 103.081, "danger_type": "flood_trapped", "num_people": 3,
  "note": "Kẹt trên mái nhà" }
```

---

## 7. Cấu hình (`.env`)

| Biến | Giá trị | Ý nghĩa |
|---|---|---|
| `WEATHER_PROVIDER` | `openmeteo` \| `mock` | Nguồn dự báo (tự fallback khi offline) |
| `LLM_PROVIDER` | `mock` \| `openai` \| `gemini` \| `local` | Model sinh bản tin |
| `TTS_PROVIDER` | `mock` \| `mms` | Đọc loa tiếng dân tộc |
| `DISPATCH_PROVIDER` | `mock` \| `live` | Kênh gửi Zalo/SMS/loa |
| `HUMAN_APPROVAL_MIN_LEVEL` | `3` | Cấp ≥ số này phải người duyệt mới gửi |
| `DB_BACKEND` | `memory` \| `supabase` | Lưu in-memory hay Postgres |
| `SUPABASE_URL`, `SUPABASE_KEY` | | Khi dùng Supabase (key = service_role) |
| `JWT_SECRET` | chuỗi bí mật | Ký token đăng nhập |

Mặc định tất cả là `mock`/`memory` → chạy ngay, không cần key.

---

## 8. Dùng Supabase (lưu Postgres + realtime cho FE)

1. Tạo project Supabase → **SQL Editor** → chạy toàn bộ `db/schema.sql` (tạo 9 bảng).
2. Điền `.env`: `DB_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_KEY` (service_role).
3. Chạy `6.1 /dev/seed` → dữ liệu tự đẩy lên Supabase (và tự kéo về khi khởi động lại).

**Realtime cho Frontend:** backend đã ghi vào Supabase mỗi khi có thay đổi (chạy nền,
không làm chậm API). FE chỉ cần **subscribe Supabase Realtime**:
```js
supabase.channel('sos')
  .on('postgres_changes',
      { event: '*', schema: 'public', table: 'rescue_requests' },
      payload => updateDashboard(payload.new))
  .subscribe()
```
(nhớ bật bảng trong Supabase → Database → Replication → publication `supabase_realtime`).

---

## 9. Deploy lên Render

- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command** (BẮT BUỘC đúng — nếu sai sẽ báo *"No open ports"*):
  ```
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- **Environment**: đặt `DB_BACKEND`, `SUPABASE_URL`, `SUPABASE_KEY`, `JWT_SECRET`
  (file `.env` KHÔNG được commit nên phải khai báo ở đây).

Đã có sẵn `Procfile` và `render.yaml` với cấu hình đúng.

---

## 10. Cây thư mục

```
backend/
├── app/
│   ├── main.py               # điểm vào FastAPI + startup (auto-seed / pull Supabase)
│   ├── config.py             # đọc .env
│   ├── security.py           # JWT + HTTP Bearer
│   ├── schemas/              # kiểu dữ liệu Pydantic (geo, citizen, admin, alert,
│   │                         #   notification, shelter, rescue, forecast, common)
│   ├── services/             # kho dữ liệu in-memory + logic
│   │   ├── geo_data.py        #   45 xã + toạ độ + haversine
│   │   ├── citizens.py / admins.py / shelters.py / notifications.py
│   │   ├── alerts.py / rescue.py
│   │   ├── seed.py            #   sinh công dân + cán bộ mẫu
│   │   └── supabase_repo.py   #   đẩy/kéo Supabase (chạy nền)
│   ├── agents/
│   │   ├── risk_engine.py     #   ngưỡng QĐ18 (tất định)
│   │   └── orchestrator.py    #   điều phối bản tin + gửi + human-loop
│   ├── providers/            # weather, llm, tts, dispatch (đều có bản mock)
│   └── api/routes/           # auth, forecast, citizens, admins, alerts,
│                             #   notifications, shelters, rescue, dev
├── db/schema.sql             # 9 bảng Postgres cho Supabase
├── requirements.txt
├── Procfile / render.yaml    # cấu hình deploy Render
└── .env.example
```

---

## 11. Câu hỏi hay gặp

- **Login báo 401?** → sai mã xã trong email, hoặc mật khẩu khác `123456`.
- **SOS báo 500?** → đã fix; nhớ dùng bản mới. Body chỉ cần `lat/lon/danger_type`.
- **Data không lên Supabase?** → kiểm tra `DB_BACKEND=supabase` và đã chạy `db/schema.sql`.
- **Render "No open ports"?** → sửa Start Command thành `--host 0.0.0.0 --port $PORT`.
- **Muốn dữ liệu bền sau restart?** → bật Supabase; nếu chạy `memory` thì mỗi lần khởi
  động lại sẽ tự seed mới.
