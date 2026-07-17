import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Leaflet owns an imperative DOM container; avoid React dev-mode double mounting it.
  reactStrictMode: false,
};

export default nextConfig;
