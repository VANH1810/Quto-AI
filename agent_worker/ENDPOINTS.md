# API Endpoints — Backend AI cảnh báo (agent_worker)

FastAPI của agent_worker, cổng **8100**. Gọi **1 lần có kết quả ngay** (không polling).

- Base URL: `http://localhost:8100` · Swagger: `http://localhost:8100/docs`
- Không cần token (control-plane nội bộ).

| Method | Endpoint | Ý nghĩa |
|--------|----------|---------|
| `POST` | `/seed` | Nạp dữ liệu mẫu (dân/cán bộ/nơi trú ẩn) |
| `POST` | `/warnings` | **Tạo cảnh báo cho 1 xã** — AI chạy ngay, trả bản tin |
| `POST` | `/warnings/{warning_id}/approve` | Cán bộ **duyệt & gửi** (cảnh báo cấp cao) |
| `POST` | `/warnings/{warning_id}/reject` | Cán bộ **bác bỏ** |
| `GET`  | `/citizens?commune_code=` | Danh sách công dân theo xã |
| `GET`  | `/admins?commune_code=` | Cán bộ phụ trách xã |
| `GET`  | `/shelters/nearest?commune_code=&lat=&lon=` | Nơi trú ẩn gần nhất |
| `GET`  | `/notifications?warning_id=` | Tin nhắn đã gửi tới từng người dân |
| `GET`  | `/health` | Kiểm tra sống |

---

## Luồng dùng (3 bước, không polling)

```
1) POST /seed                          # nạp dữ liệu (1 lần)
2) POST /warnings {commune_code}       # → trả luôn: risk_level + bản tin vi/tai/hmn + status
3) (nếu status=pending_approval)
   POST /warnings/{warning_id}/approve # → gửi đa kênh
```

---

## `POST /warnings` — Tạo cảnh báo (AI chạy ngay)

Quét nguy cơ → risk engine (QĐ18) → khuyến nghị → LLM soạn bản tin đa ngữ. **Chờ xong,
trả kết quả trong response** (worker Celery chạy nền, API đợi hộ).

- Cấp thấp (<3): tự gửi → `status="dispatching"`.
- Cấp cao (≥3): chờ duyệt → `status="pending_approval"`.

**Request:**
```json
{ "commune_code": "muong_pon", "langs": ["vi","tai","hmn"] }
```
Ép cấp cao để test (kèm mưa 250mm):
```json
{ "commune_code": "muong_pon", "langs": ["vi","tai","hmn"],
  "forecast": { "commune_code":"muong_pon","commune_name":"Xã Mường Pồn","lat":21.53,"lon":103.08,
    "elevation_m":720,"source":"MOCK","updated_at":"2026-07-18",
    "days":[{"date":"2026-07-18","precip_mm":250,"temp_min_c":23,"temp_max_c":30,"temp_mean_c":26,"wind_max_kmh":30,"humidity_mean":95,"visibility_min_m":3000},
            {"date":"2026-07-19","precip_mm":250,"temp_min_c":23,"temp_max_c":30,"temp_mean_c":26,"wind_max_kmh":30,"humidity_mean":96,"visibility_min_m":2500},
            {"date":"2026-07-20","precip_mm":250,"temp_min_c":22,"temp_max_c":28,"temp_mean_c":25,"wind_max_kmh":35,"humidity_mean":97,"visibility_min_m":2000}] } }
```

**Response (cấp cao):**
```json
{ "warning_id": "alt_xxxx", "status": "pending_approval", "risk_level": 4, "needs_human": true,
  "top_event": {"hazard":"flash_flood","risk_level":4,"risk_label":"Cấp 4 · Rất lớn"},
  "bulletins": [ {"lang":"vi","title":"🌊 CẢNH BÁO LŨ QUÉT — Xã Mường Pồn","body":"..."},
                 {"lang":"tai","title":"...","body":"..."}, {"lang":"hmn","title":"...","body":"..."} ],
  "actions": ["Rời ngay khỏi bờ suối","Di chuyển lên chỗ cao","..."],
  "n_recipients": 3 }
```

```bash
curl -X POST http://localhost:8100/warnings \
  -H "Content-Type: application/json" \
  -d '{"commune_code":"muong_pon","langs":["vi","tai","hmn"]}'
```

## `POST /warnings/{warning_id}/approve` — Duyệt & gửi
```json
{ "note": "Đồng ý phát ngay." }
```
hoặc sửa lời tiếng Việt: `{ "edited_body_vi": "CẢNH BÁO LŨ QUÉT ..." }`
→ `{ "warning_id":"alt_xxxx", "status":"dispatching", "dispatched": 3 }`

## `POST /warnings/{warning_id}/reject` — Bác bỏ
```json
{ "note": "Chờ xác minh trạm khí tượng." }
```

## Kiểm tra sau khi gửi
```bash
curl "http://localhost:8100/notifications?warning_id=alt_xxxx"   # tin cá nhân: sent + failed→đến nhà
```

---

## Chạy
```bash
cd agent_worker && docker compose up --build
# Swagger: http://localhost:8100/docs
```
