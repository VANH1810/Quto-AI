import type { Metadata } from "next";
import { Roboto } from "next/font/google";
import "./base.css";

const roboto = Roboto({
  variable: "--font-roboto",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Bản tin an toàn · Điện Biên",
  description: "Bản đồ cảnh báo thời tiết và thiên tai cấp xã tại Điện Biên",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className={`${roboto.variable} ${roboto.className}`}>{children}</body>
    </html>
  );
}
