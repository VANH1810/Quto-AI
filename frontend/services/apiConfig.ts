export function getApiBaseUrl(): string {
  const configuredUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredUrl) return configuredUrl.replace(/\/$/, "");
  if (process.env.NODE_ENV === "development") return "http://localhost:8000";
  throw new Error("NEXT_PUBLIC_API_BASE_URL chưa được cấu hình cho môi trường production.");
}
