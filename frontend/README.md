# Bản tin an toàn · Frontend prototype

Prototype Next.js độc lập cho bản đồ cảnh báo thời tiết và thiên tai cấp xã tại Điện Biên. Frontend mặc định dùng ranh giới hành chính snapshot 2025 và dữ liệu cảnh báo mock, không cần chạy backend.

## Cài đặt và chạy

Yêu cầu Node.js 20 trở lên. Trên Windows, có thể dùng `npm` đi kèm Node.js mà không cần cài thêm `pnpm`.

```bash
cd frontend
npm install
npm run dev
```

Mở [http://localhost:3000](http://localhost:3000) cho bản đồ công dân, hoặc [http://localhost:3000/admin](http://localhost:3000/admin) cho bảng điều hành nội bộ. Cả hai route chạy trong cùng một ứng dụng Next.js và cùng cổng `3000`.
Cache development được lưu trong `.next-dev`, tách biệt với build production
trong `.next` để tránh xung đột Webpack chunk khi chuyển giữa `dev`, `build` và
`start`.

Kiểm tra chất lượng trước khi bàn giao:

```bash
npm run lint
npm run typecheck
npm run build
```

Nếu muốn dùng pnpm, cài một lần bằng `npm install -g pnpm`, sau đó chạy `pnpm install` và `pnpm dev`.

## Chế độ dữ liệu

Mặc định `NEXT_PUBLIC_DATA_SOURCE=mock`. Dữ liệu nằm tại:

- `public/data/dien-bien-province.geojson`: polygon giới hạn tỉnh Điện Biên.
- `public/data/dien-bien-communes.geojson`: 45 xã/phường mới có hiệu lực từ 01/07/2025. Mã xã dùng danh mục tại Quyết định 19/2025/QĐ-TTg; hình học là snapshot OpenStreetMap và cần được cơ quan chuyên môn thẩm định trước khi dùng cho nghiệp vụ chính thức.
- `data/mockAlerts.ts`: cảnh báo và cấp nguy hiểm 1-5.
- `data/shelters.ts`: điểm trú ẩn và metadata nguồn nội bộ.

Làm mới snapshot ranh giới từ các OSM relation đã đối chiếu:

```bash
npm run data:refresh-boundaries
```

Script nguồn nằm ở `scripts/fetch-dien-bien-boundaries.mjs`. Sau khi làm mới, cần kiểm tra đủ 45 feature và đối chiếu lại mã/tên với danh mục hành chính hiện hành.

Để dùng API FastAPI hiện có, sao chép `.env.example` thành `.env.local` và đổi:

```env
NEXT_PUBLIC_DATA_SOURCE=api
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`services/dataSource.ts` triển khai cùng một `AlertDataSource` cho mock và backend; component chỉ nhận các kiểu dữ liệu chuẩn hóa trong `types/`. Route `/admin` gọi API điều hành tại `NEXT_PUBLIC_API_BASE_URL`, trong khi route bản đồ vẫn tôn trọng `NEXT_PUBLIC_DATA_SOURCE`. Khi chạy local, backend cần cho phép CORS từ `http://localhost:3000`.

## Console điều hành

Các route vận hành dùng cùng ứng dụng: `/admin`, `/admin/alerts`, `/admin/risks`, `/admin/delivery`, `/admin/speakers` và `/admin/audit`.

Để trình diễn độc lập với backend, đặt rõ ràng trong `.env.local`:

```env
NEXT_PUBLIC_USE_MOCKS=true
```

Mock chỉ được bật bằng biến môi trường này; không tự chuyển sang mock khi API trả lỗi xác thực hoặc lỗi máy chủ. Chế độ mock gán admin demo cho bốn xã Sín Thầu, Nậm Kè, Quảng Lâm, Na Sang và có hai nhóm cần liên hệ trực tiếp được tách theo `alertId`.

## Cấu trúc

```text
frontend/
├── app/          # Next.js App Router và CSS responsive
├── components/   # Bản đồ, thanh tìm kiếm, chú giải, panel chi tiết
├── data/         # Dữ liệu cảnh báo và điểm trú ẩn mock
├── hooks/        # Tải dữ liệu và Geolocation API
├── public/data/  # GeoJSON tỉnh và 45 xã/phường Điện Biên
├── scripts/      # Script làm mới snapshot ranh giới
├── services/     # Service/API layer có thể thay thế
├── types/        # Hợp đồng TypeScript dùng chung
└── utils/        # Metadata mức rủi ro và hàm địa lý
```

## Lưu ý prototype

- Bản đồ nền dùng OpenStreetMap nên cần kết nối mạng để tải tile; polygon GeoJSON, marker trú ẩn, vị trí người dùng và dữ liệu cảnh báo vẫn thuộc frontend.
- Geolocation chỉ hoạt động trên `localhost` hoặc HTTPS và cần người dùng cấp quyền.
- OpenStreetMap là nguồn mở do cộng đồng đóng góp, không phải hồ sơ địa chính pháp lý. Trước khi triển khai vận hành cảnh báo chính thức, cần đối chiếu snapshot với dữ liệu địa giới do cơ quan nhà nước có thẩm quyền cung cấp.
- Dữ liệu cảnh báo, dân số tham khảo và điểm trú ẩn hiện vẫn là mock; thay chúng bằng dữ liệu backend đã xác minh trước khi sử dụng thực tế.
