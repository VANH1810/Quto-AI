# data-pipeline — Fetch & xử lý dự báo 7 ngày (Điện Biên)

Pipeline **tách riêng** khỏi backend API: lấy dữ liệu dự báo **7 ngày tới** cho 45 xã,
tách điểm theo tâm xã + độ cao, rồi **hiệu chỉnh sai số (bias correction)** theo từng xã.

Đây là nhánh **phải** của sơ đồ kiến trúc:

```
                 ┌──────────────────────────────┐
                 │   Fetch (hourly tick)         │   ← python -m pipeline.run --loop
                 │   Open-Meteo (+ IMERG/trạm*)  │
                 └───────────────┬──────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │   Point extract (7-day)       │   pipeline/fetch.py
                 │   Centroid + elevation param  │
                 └───────────────┬──────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │   Bias correction             │   pipeline/bias_correction.py
                 │   Quantile map per commune    │
                 └───────────────┬──────────────┘
                                 │
                                 ▼
                 output/forecast_<xã>.json + output/latest.json
```

\* IMERG (mưa vệ tinh) + trạm KTTV + nhánh nowcasting (regrid 0.04° → build features) là
**roadmap** — xem mục 6. Bản này đúng như yêu cầu: **chỉ fetch 7 ngày tới**.

---

## 1. Chạy

```bash
cd data-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m pipeline.run          # chạy 1 lần
python -m pipeline.run --loop   # chạy lặp mỗi 60 phút (hourly tick)
```

Kết quả ghi vào `output/`.

---

## 2. Các bước (khớp sơ đồ)

| Bước trong sơ đồ | File | Làm gì |
|---|---|---|
| **Fetch (hourly tick)** | `pipeline/run.py --loop` | Vòng lặp gọi lại mỗi `FETCH_INTERVAL_MINUTES` phút |
| **Point extract (7-day)** | `pipeline/fetch.py` | Gọi Open-Meteo tại `lat/lon` tâm xã + tham số `elevation` (hiệu chỉnh nhiệt/áp theo độ cao). Offline → sinh dữ liệu synthetic để không chết |
| **Bias correction** | `pipeline/bias_correction.py` | **Quantile mapping** theo từng xã: ánh xạ giá trị mô hình → giá trị đã hiệu chỉnh bằng cặp phân vị `model_q → obs_q` |

---

## 3. Đầu ra

`output/forecast_<mã_xã>.json` — mỗi xã 7 ngày:
```json
{
  "commune_code": "muong_pon",
  "commune_name": "Xã Mường Pồn",
  "lat": 21.53, "lon": 103.08, "elevation_m": 720,
  "source": "Open-Meteo best_match (point extract + elevation) + bias-corrected (quantile map)",
  "generated_at": "2026-07-18 10:02:38",
  "days": [
    {
      "date": "2026-07-18",
      "precipitation_sum": 14.48,        // đã hiệu chỉnh
      "precipitation_sum_raw": 11.1,     // giá trị gốc từ mô hình
      "temperature_2m_min": 21.7,
      "temperature_2m_max": 29.5,
      "temperature_2m_mean": 25.6,
      "wind_speed_10m_max": 12.4
    }
  ]
}
```
`output/latest.json` — gộp tất cả 45 xã (cho backend/FE đọc nhanh).

> Giữ cả `*_raw` và giá trị đã hiệu chỉnh để dễ so sánh/kiểm toán.

---

## 4. Bias correction hoạt động thế nào

File `data/quantile_maps.json`:
```json
{
  "muong_pon": {
    "precipitation_sum": { "model_q": [0,10,30,60,120,200], "obs_q": [0,13,40,78,150,245] }
  }
}
```
- Với mỗi giá trị mưa mô hình, nội suy tuyến tính theo cặp `model_q → obs_q`.
- Xã/biến **không có** trong file → **giữ nguyên** (identity), an toàn.
- 3 ví dụ mẫu (Mường Pồn, Tủa Chùa, Sín Thầu) là **minh hoạ** (vùng cao thường bị dự
  báo hụt mưa). Thay bằng số thật khi có dữ liệu trạm:

```python
from pipeline.bias_correction import train_quantile_map
# model_series, obs_series: mưa mô hình vs mưa trạm đo (cùng thời điểm, lịch sử)
m = train_quantile_map(model_series, obs_series, n_quantiles=11)
# → dán m vào data/quantile_maps.json cho xã tương ứng
```

---

## 5. Nối với backend

Pipeline này **độc lập** với backend API. Ba cách dùng đầu ra:
1. Backend đọc `output/latest.json` thay cho gọi Open-Meteo trực tiếp (dữ liệu đã hiệu chỉnh, ổn định hơn).
2. Đẩy `output/` lên Supabase Storage / bảng `forecast` để FE dùng.
3. Chạy như cron/worker riêng (Render Cron Job hoặc `--loop`).

Danh mục 45 xã ở `data/communes.json` **đồng bộ** với backend (`app/services/geo_data.py`).
Nếu backend thêm/sửa xã, chạy lại lệnh sinh file (xem cuối README).

---

## 6. Roadmap (nhánh trái của sơ đồ — chưa làm ở bản này)

- **IMERG** (mưa vệ tinh NASA) + **trạm KTTV Điện Biên** làm nguồn bổ sung/ground-truth.
- **Align to grid (0–6h)**: regrid về lưới 0.04°, chuẩn UTC, vá khoảng trống → **build
  features** (cùng code với lúc train) → chạy model **nowcasting** 0–6h (XGBoost/LSTM).
- Bản hiện tại tập trung **point extract 7 ngày + bias correction** — đúng phạm vi yêu cầu.

---

## 7. Cấu trúc

```
data-pipeline/
├── pipeline/
│   ├── config.py            # URL, số ngày, chu kỳ, thư mục
│   ├── communes.py          # nạp 45 xã từ data/communes.json
│   ├── fetch.py             # Point extract 7-day (Open-Meteo + elevation)
│   ├── bias_correction.py   # Quantile mapping theo xã + train_quantile_map()
│   └── run.py               # orchestrate + hourly tick (--loop)
├── data/
│   ├── communes.json        # 45 xã (code, name, lat, lon, elevation_m)
│   └── quantile_maps.json   # map hiệu chỉnh theo xã (identity nếu trống)
├── output/                  # kết quả (gitignored)
└── requirements.txt
```

Sinh lại `data/communes.json` từ backend (nếu danh mục xã đổi):
```bash
cd ../backend && source .venv/bin/activate
python -c "import json; from app.services.geo_data import all_communes; \
json.dump([{'code':c.code,'name':c.name,'lat':c.lat,'lon':c.lon,'elevation_m':c.elevation_m} \
for c in all_communes()], open('../data-pipeline/data/communes.json','w'), ensure_ascii=False, indent=2)"
```
