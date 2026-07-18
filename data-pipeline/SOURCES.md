# Nguồn dữ liệu & trích dẫn (data-pipeline)

Tài liệu này liệt kê **nguồn gốc từng loại dữ liệu** để trình bày minh bạch với giám khảo.
Nguyên tắc: cái gì **thật/có nguồn** thì ghi rõ; cái gì **xấp xỉ/minh hoạ** cũng ghi rõ.

## 1. Dự báo thời tiết (THẬT)
- **Open-Meteo Forecast API** — https://open-meteo.com/
- Mô hình: ECMWF IFS, DWD ICON, GFS (chọn tự động qua `best_match`).
- Giấy phép: **CC BY 4.0**, miễn phí, không cần API key.
- Cách dùng: gọi tại toạ độ tâm mỗi xã + tham số `elevation` cho 7 ngày.

## 2. Hạ quy mô theo độ cao (THẬT)
- **Copernicus GLO-90 DEM** (mô hình độ cao số 90 m) — dùng gián tiếp qua tham số
  `elevation` của Open-Meteo (hiệu chỉnh nhiệt/áp theo độ cao — hypsometric).
- Nguồn: Copernicus / ESA — https://spacedata.copernicus.eu/

## 3. Toạ độ & độ cao các xã (MỘT PHẦN thật, có gắn nhãn tin cậy)
- **Open-Meteo Geocoding API** → dữ liệu **GeoNames** (CC BY 4.0)
  - https://open-meteo.com/en/docs/geocoding-api · https://www.geonames.org/
- Kết quả đối soát (xem `data/geocode_report.json`): mỗi xã có `coord_confidence` =
  `high` / `medium` / `low` và `coord_source`.
- **Lưu ý trung thực:** do **sáp nhập đơn vị hành chính 2025**, nhiều tên xã mới chưa có
  trong GeoNames → các xã `low` **giữ toạ độ xấp xỉ (gõ tay)** và được đánh dấu rõ, chờ
  đối chiếu **ranh giới hành chính chính thức**.
- Nâng cấp đề xuất: GADM (https://gadm.org/) hoặc OpenStreetMap (© OpenStreetMap
  contributors, ODbL) — dùng centroid ranh giới thật.

## 4. Ngưỡng rủi ro thiên tai (PHÁP LÝ)
- **Quyết định 18/2021/QĐ-TTg** — quy định cấp độ rủi ro thiên tai (mưa lớn, lũ quét,
  sạt lở, rét hại…). Đây là căn cứ pháp lý cho risk engine (thang màu 1–5).

## 5. Bias correction — quantile mapping (CƠ CHẾ thật, SỐ minh hoạ)
- Phương pháp **quantile mapping** là kỹ thuật hiệu chỉnh sai số/hạ quy mô thống kê
  tiêu chuẩn (ánh xạ phân vị mô hình → phân vị quan trắc).
- **Hiện trạng:** bảng hiệu chỉnh mới có ở 3 xã và là **số minh hoạ**. Để có số THẬT cần
  **dữ liệu trạm KTTV Điện Biên** (Đài KTTV khu vực / Ban Chỉ huy PCTT&TKCN tỉnh) rồi
  chạy `train_quantile_map(model_series, obs_series)`.

## 6. Roadmap — nguồn bổ sung (chưa tích hợp)
- **NASA GPM IMERG** (mưa vệ tinh) — https://gpm.nasa.gov/data/imerg
- **Trạm KTTV Điện Biên** (quan trắc mặt đất) — ground-truth cho bias correction.
- **SeAFFGS / VNMHA** (hướng dẫn lũ quét khu vực Đông Nam Á).

---

### Tóm tắt để nói với giám khảo
> "Dự báo thời tiết cho cả 45 xã là **thật** (Open-Meteo, CC BY 4.0, mô hình ECMWF/ICON/GFS),
> có hiệu chỉnh độ cao (Copernicus GLO-90). Toạ độ lấy từ **GeoNames** và **gắn nhãn độ
> tin cậy từng xã** — chúng tôi **không giấu** việc sáp nhập xã 2025 khiến một số xã phải
> giữ toạ độ xấp xỉ, và có lộ trình thay bằng ranh giới hành chính chính thức. Ngưỡng cảnh
> báo theo **QĐ18/2021/QĐ-TTg**. Bias correction đã có cơ chế, chờ dữ liệu trạm KTTV để
> hiệu chỉnh thật."
