import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function nextConfig(phase: string): NextConfig {
  return {
    // Keep development chunks isolated from production chunks. Mixing them can
    // leave Webpack loading an entry against an incompatible runtime.
    distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
    reactStrictMode: true,
    poweredByHeader: false,
    productionBrowserSourceMaps: false,
    images: {
      formats: ["image/avif", "image/webp"],
      minimumCacheTTL: 2_678_400,
    },
    async headers() {
      return [
        {
          source: "/:path*",
          headers: [
            { key: "X-Content-Type-Options", value: "nosniff" },
            { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
            { key: "Permissions-Policy", value: "geolocation=(self)" },
          ],
        },
        {
          source: "/data/:path*",
          headers: [
            { key: "Cache-Control", value: "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800" },
          ],
        },
      ];
    },
  };
}
