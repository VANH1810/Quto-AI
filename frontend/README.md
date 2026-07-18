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

Client chỉ gọi các route cùng origin dưới `/api/data`; fixture không còn được import vào Client Components. Nguồn được chọn bên server bằng `APP_DATA_SOURCE`:

- `local`: fixture trong repo, chỉ bundle vào server output; phù hợp phát triển local.
- `blob`: snapshot JSON trong Private Vercel Blob; URL và credential không được gửi xuống browser.
- `api`: Vercel Function gọi FastAPI qua `APP_BACKEND_URL`.

Không dùng `NEXT_PUBLIC_*` cho lựa chọn nguồn hoặc Blob credential. Dữ liệu đã trả cho UI vẫn có thể xem trong Network tab; gateway bảo vệ fixture gốc, URL storage, credential và cấu hình triển khai, chứ không thể làm dữ liệu hiển thị trở nên vô hình.

Làm mới snapshot ranh giới từ các OSM relation đã đối chiếu:

```bash
npm run data:refresh-boundaries
```

Script nguồn nằm ở `scripts/fetch-dien-bien-boundaries.mjs`. Sau khi làm mới, cần kiểm tra đủ 45 feature và đối chiếu lại mã/tên với danh mục hành chính hiện hành.

Để dùng API FastAPI hiện có, sao chép `.env.example` thành `.env.local` và đổi:

```env
APP_DATA_SOURCE=api
APP_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`services/dataSource.ts` chỉ gọi gateway. `server/dataGateway.ts` chuẩn hóa cả ba nguồn về các kiểu trong `types/`. `NEXT_PUBLIC_API_BASE_URL` chỉ còn phục vụ luồng đăng nhập/kiểm tra phiên admin trực tiếp từ browser; backend cần cho phép CORS cho các request đó.

## Console điều hành

Các route vận hành dùng cùng ứng dụng: `/admin`, `/admin/alerts`, `/admin/risks`, `/admin/delivery`, `/admin/speakers` và `/admin/audit`.

Các route quản trị cũng dùng gateway này. Gateway không tự fallback từ `api` sang `local` hoặc `blob` khi backend lỗi, tránh che giấu sự cố production.

## Deploy trên Vercel

Khi import repository vào Vercel, đặt **Root Directory** là `frontend`. Vercel sẽ dùng `vercel.json`, chạy `npm ci` rồi `npm run build`; App Router tự phục vụ `/`, `/admin` và toàn bộ route con, không cần rewrite SPA.

Thiết lập biến môi trường cho cả Production và Preview:

| Biến | Backend thật | Private Blob |
|---|---|---|
| `APP_DATA_SOURCE` | `api` | `blob` |
| `APP_BACKEND_URL` | URL HTTPS của FastAPI | Không cần |
| `APP_DATA_BLOB_URL` | Không cần | URL private đầy đủ của snapshot |
| `NEXT_PUBLIC_API_BASE_URL` | URL HTTPS cho login/session admin | URL HTTPS cho login/session admin |

Nếu dùng backend thật, thêm domain Production/Preview của Vercel vào `CORS_ORIGINS` phía FastAPI cho login/session admin. Không đưa khóa bí mật vào biến có tiền tố `NEXT_PUBLIC_`. Thay đổi env trên Vercel chỉ áp dụng cho deployment mới nên cần redeploy.

Trước khi deploy hoặc promote Preview sang Production, chạy:

```bash
npm ci
npm run lint
npm run typecheck
npm run build
```

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
## Tạo Private Blob snapshot

1. Ở local, đặt `APP_DATA_SOURCE=local` và `ALLOW_MOCK_SNAPSHOT_EXPORT=true`, rồi chạy dev server.
2. Chạy `npm run data:export-mocks`; file `quto-data.snapshot.json` được tạo và đã nằm trong `.gitignore`.
3. Trong Vercel Storage, tạo Blob store với access `Private` và connect store với project.
4. Upload snapshot:

   ```bash
   vercel blob put quto-data.snapshot.json --access private --content-type application/json
   ```

5. Trên Vercel đặt `APP_DATA_SOURCE=blob` và `APP_DATA_BLOB_URL` bằng URL private đầy đủ của file. Khi store đã connect, Vercel Function dùng OIDC tự động; local có thể dùng `BLOB_READ_WRITE_TOKEN` trong `.env.local`.
6. Redeploy vì thay đổi environment variables chỉ áp dụng cho deployment mới.

Để chuyển sang backend thật, chỉ cần đặt `APP_DATA_SOURCE=api` và `APP_BACKEND_URL`; client/UI không đổi.
