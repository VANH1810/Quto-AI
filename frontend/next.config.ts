import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function nextConfig(phase: string): NextConfig {
  return {
    // Keep development chunks isolated from production chunks. Mixing them can
    // leave Webpack loading an entry against an incompatible runtime.
    distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
    // Leaflet owns an imperative DOM container; avoid React dev-mode double mounting it.
    reactStrictMode: false,
  };
}
