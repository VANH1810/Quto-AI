# Pipeline cảnh báo sớm — mô tả black-box cho teammate

## Nó làm gì?

Chạy 1 lệnh duy nhất → module tự động: lấy dữ liệu thời tiết thật (Open-Meteo)
cho 3 xã Điện Biên → chạy model nowcast (LSTM) + forecast 7 ngày → đưa qua
risk engine (ngưỡng QĐ 18/2021) → **xuất ra file đánh giá rủi ro + CAP XML
trên đĩa**. Hết. Nó KHÔNG gửi tin đi đâu cả — việc sinh bản tin (LLM) và
dispatch (Zalo/SMS/loa) là bước SAU, đọc từ output của nó.

```
Open-Meteo ──► nowcast + forecast ──► risk engine ──► runs/<run>/tick_NN/assessments.json
                                                      (+ cap_*.xml)
```

## Output ở đâu, format thế nào?

Mỗi lần chạy tạo 1 thư mục `runs/<timestamp>_<mode>/tick_NN/`. File cần quan
tâm duy nhất: **`assessments.json`** — mảng `assessments`, mỗi phần tử là 1
đánh giá cho 1 loại thiên tai của 1 xã:

```jsonc
{
  "commune_code": "03136",            // xã (Mường Pồn)
  "hazard_type": "lu_quet_sat_lo",    // loại: lu_quet_sat_lo | mua_lon | ret_hai | suong_mu | heartbeat
  "risk_level": 2,                    // cấp 0–5 theo QĐ18
  "risk_color": "vang_nhat",          // màu hiển thị
  "msg_type": "Alert",                // Alert = mới | Update | Cancel = hết
  "output_class": "public_warning",   // QUAN TRỌNG: chỉ public_warning mới được gửi cho dân;
                                      // official_advisory = chỉ cán bộ; heartbeat = bỏ qua
  "requires_human_approval": false,   // true (cấp ≥3) → PHẢI chờ admin duyệt mới dispatch
  "onset_estimate": "...", "expires": "...",
  "status": "Exercise",               // "Exercise" = diễn tập, hiển thị banner, KHÔNG gửi thật
  "triggered_rules": [ ... ],         // điều luật + số liệu kích hoạt (để giải trình)
  "derived": { "eff_rain_24h": 150.0, ... },
  "provenance": { ... },              // nguồn dữ liệu, model, giờ fetch → làm dòng "Nguồn: ..."
  "cap_xml": "<alert ...>"            // bản CAP 1.2 chuẩn quốc tế, kèm sẵn
}
```

Kèm theo trong cùng thư mục: `cap_<xã>_<hazard>.xml` (CAP XML tách file),
`risk_input_*.json` / `raw_api/` (dữ liệu gốc để audit/replay).

## Deploy đơn giản nhất

```bash
# 1 lần duy nhất: tạo env (Python 3.11 + TF, ~2 phút)
uv venv .venv-tf3 --python 3.11
uv pip install --python .venv-tf3/bin/python -r requirements-tf.txt

# chạy 1 tick với dữ liệu THẬT (~10 giây, 5 HTTP request)
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --source live --ticks 1
```

Console in ra tóm tắt từng tick; kết quả nằm ở dòng `artifacts runs/...`.

Muốn demo có cảnh báo thật sự (trời đang đẹp thì live chỉ ra heartbeat):

```bash
# kịch bản bão Mường Pồn: Alert cấp 2 → cấp 4 → khuyến nghị hạ
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --source scenario --scenario storm --ticks 8
```

Lưu ý an toàn: mặc định mọi output là `status: "Exercise"` (diễn tập). Banner
`!! SCALER=DUMMY !!` nghĩa là số liệu nowcast chưa có ý nghĩa vật lý (chờ
retrain scaler) — cứ kệ nó, engine không phụ thuộc.

## Bước tiếp theo (việc của teammate)

Đọc `assessments.json` → lọc theo `output_class` + `requires_human_approval` +
`status` → đưa từng object vào LLM `generate_bulletin(...)` để sinh bản tin
Việt/Thái/Mông → TTS → dispatch Zalo/SMS/loa. Object này là contract ổn định;
không cần biết bên trong pipeline làm gì.
