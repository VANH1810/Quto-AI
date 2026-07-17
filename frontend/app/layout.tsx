import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bản tin an toàn · Điện Biên",
  description: "Bản đồ cảnh báo thời tiết và thiên tai cấp xã tại Điện Biên",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
