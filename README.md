# BẢN TIN AN TOÀN — Backend (Điện Biên Early-Warning System)

Backend AI-Agent cảnh báo sớm thiên tai **cấp xã** cho Điện Biên: hạ quy mô dự báo
thời tiết về từng xã, chấm rủi ro theo **QĐ18/2021/QĐ-TTg**, sinh bản tin đa ngữ
(Việt / Thái / Mông) và gửi đa kênh (Zalo ZNS / SMS / loa) — có **human-in-the-loop**
khi cấp cao và **gửi lại / đến tận nhà** khi lỗi.

> FastAPI + Swagger. Mặc định chạy **full mock, không cần API key**.

## Chạy nhanh
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # tuỳ chọn; mặc định đã ổn
uvicorn app.main:app --reload   # → http://localhost:8000/docs
```

## Luồng demo (bấm theo số tag trên Swagger)
1. `6.1 POST /dev/seed` → tạo 1 admin + công dân mẫu (Thái/Mông/Kinh).
2. `1.2 POST /auth/login` với `canbo@dienbien.gov.vn` / `123456` → **Authorize**.
3. `2.1 /communes`, `2.2 /forecast/{code}` (7 ngày), `2.3 /risk-map` (tô màu bản đồ).
4. `6.2 POST /dev/scenario/muong-pon-2024` → tái hiện lũ quét 25/7/2024 →
   risk engine bắn **cấp 3 (cam)**, cảnh báo ở trạng thái *chờ phê duyệt*.
5. `5.4 /alerts/{id}/approve` → gửi. Loa Mường Pồn *ngoại tuyến* → `5.5 /retry`
   hoặc `5.6` xem task **đến tận nhà** (tự tạo, giao cán bộ phụ trách xã).

## Kiến trúc (source data → xử lý → phân phối)
```
Open-Meteo (ECMWF/ICON/GFS, hạ quy mô theo DEM + độ cao)  ─┐
Trạm KTTV Điện Biên / lịch sử thiên tai (roadmap)          ─┤→ providers/weather.py
                                                            │
   forecast theo xã  ──►  RISK ENGINE (deterministic, QĐ18) ──► HazardEvent(cấp 1–5, provenance)
   agents/risk_engine.py  [KHÔNG dùng LLM — minh bạch/kiểm toán]        │
                                                                        ▼
   AGENT ORCHESTRATOR (agents/orchestrator.py) — "AI-native heart":
     tool: llm.generate_bulletins (đa ngữ)  ·  tts.synthesize (loa, Meta MMS blt/mww)
     human-in-the-loop nếu cấp ≥ ngưỡng     ·  audit log từng bước (provenance)
                                                                        │
                                                                        ▼
   DISPATCH đa kênh (providers/dispatch.py): Zalo ZNS · SMS brandname · loa IP
     lỗi → retry / tạo HomeVisitTask (đến tận nhà báo)
```

### Các cơ sở dữ liệu
- **DB1 · Công dân** (`services/citizens.py`, khoá = **CCCD**): tên, tuổi, địa chỉ,
  SĐT, dân tộc, tôn giáo, xã, toạ độ, `consent_zalo_sms` (NĐ13/2023). `preferred_lang`
  suy ra từ dân tộc. Mô phỏng đồng bộ từ CSDL dân cư quốc gia.
- **DB2 · Admin/Cán bộ** (`services/admins.py`): tên, tuổi, SĐT, dân tộc, tôn giáo,
  vai trò (thôn/xã/tỉnh), danh sách **xã phụ trách**. Đăng nhập JWT, duyệt bản tin,
  nhận task đến nhà. `for_commune()` → chọn cán bộ giao việc khi gửi lỗi.
- **DB3 · Tin nhắn cá nhân** (`services/notifications.py`): mỗi lần gửi cảnh báo tạo
  1 bản ghi cho **từng công dân** — kênh, ngôn ngữ, trạng thái (sent/failed) + **địa chỉ
  nhà** + **nơi trú ẩn an toàn gần nhất**. `failed_only` → danh sách ai chưa nhận để đến nhà.
- **Nơi trú ẩn** (`services/shelters.py`): điểm sơ tán theo xã (trường/nhà văn hoá/UBND/
  điểm cao) có địa chỉ + toạ độ; `nearest()` tính điểm gần nhà nhất (haversine).

### Supabase (tuỳ chọn — thay in-memory bằng Postgres)
Mặc định `DB_BACKEND=memory` (chạy ngay). Để dùng Supabase:
1. Tạo project Supabase → **SQL Editor** → chạy `db/schema.sql` (tạo 7 bảng: communes,
   citizens, admins, shelters, alerts, notifications, home_visits).
2. Điền `.env`: `DB_BACKEND=supabase`, `SUPABASE_URL=...`, `SUPABASE_KEY=<service_role>`.
3. `6.1 /dev/seed` → `6.3 POST /dev/supabase/push-seed` để **đẩy** xã/công dân/trú ẩn lên.
   Từ đó tin nhắn (notifications) tự đẩy lên Supabase mỗi khi gửi cảnh báo; lúc khởi động
   app tự **kéo** công dân + nơi trú ẩn từ Supabase về.

### Cấp độ rủi ro (thang màu QĐ18/2021)
`1` xanh · `2` vàng · `3` cam · `4` đỏ · `5` tím. Ngưỡng ở
`agents/risk_engine.py::RULES` (mưa 24h, mưa dồn/đất bão hoà, độ nhạy cảm sạt lở xã,
rét hại <13°C, sương muối, sương mù) — **chỉnh được, có thể đưa ra DB/.env**.

## Cấu hình (`.env`)
| Biến | Giá trị | Ý nghĩa |
|---|---|---|
| `WEATHER_PROVIDER` | `openmeteo` \| `mock` | Open-Meteo thật (tự fallback synthetic khi offline) |
| `LLM_PROVIDER` | `mock` \| `openai` \| `gemini` \| `local` | Sinh/dịch bản tin |
| `TTS_PROVIDER` | `mock` \| `mms` | Đọc loa tiếng dân tộc (Meta MMS `blt`/`mww`) |
| `DISPATCH_PROVIDER` | `mock` \| `live` | Cắm Zalo ZNS / SMS / loa IP thật |
| `HUMAN_APPROVAL_MIN_LEVEL` | `3` | Cấp ≥ giá trị này phải người duyệt mới gửi |
| `DB_BACKEND` | `memory` \| `supabase` | Lưu in-memory hay Postgres (Supabase) |
| `SUPABASE_URL` / `SUPABASE_KEY` | | URL + service_role key khi dùng Supabase |

## Bản đồ đường dẫn API
| Nhóm | Endpoint chính |
|---|---|
| 1 Tài khoản | `auth/register` `auth/login` `auth/me` |
| 2 Bản đồ & Dự báo | `communes` · `forecast/{code}` · `risk-map` |
| 3 DB1 Công dân | `GET/POST citizens` · `citizens/{cccd}` |
| 4 DB2 Cán bộ | `GET admins` |
| 5 Cảnh báo (Agent) | `alerts/scan/{code}` · `alerts` · `alerts/{id}/approve` · `/retry` · `tasks/home-visits` |
| 6 Demo | `dev/seed` · `dev/scenario/muong-pon-2024` · `dev/supabase/push-seed` |
| 7 Nơi trú ẩn | `shelters` · `shelters/nearest` |
| 8 DB3 Tin nhắn | `notifications?alert_id=&cccd=&failed_only=` |
| 9 Hệ thống | `health` |

## Roadmap (ngoài phạm vi 48h)
- Thay in-memory → PostgreSQL + PostGIS (ranh giới xã thật, DEM Copernicus GLO-90).
- Nowcasting model của team (XGBoost/Stacked-LSTM) huấn luyện lại trên dữ liệu Điện Biên.
- Bật Meta MMS TTS thật (kiểm tra vocab `blt` Tai Viet vs romanized) + audio cộng đồng thu sẵn.
- Cắm Zalo OA/ZNS + SMS brandname + API loa IP (Việt Hưng/VNPT/Viettel), xuất **CAP-XML**.
- Lộ các tool của orchestrator qua **MCP server** (get_forecast/get_risk/generate_bulletin/dispatch).
- Tuân thủ Luật ANM 2018 + NĐ13/2023 (host tại VN, consent, opt-out, xử lý khẩn cấp Điều 13).
```
