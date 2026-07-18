import type { Metadata } from "next";
import "../globals.css";
import "./forecast.css";
import { RegionalForecast } from "@/components/forecast/RegionalForecast";

export const metadata: Metadata = {
  title: "Dự báo khu vực · Điện Biên",
  description: "Dự báo thời tiết và mức độ rủi ro thiên tai trong 7 ngày tại Điện Biên",
};

export default function ForecastPage() {
  return <RegionalForecast />;
}
