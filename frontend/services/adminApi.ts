import { adminRequest } from "@/services/adminClient";

export async function connectDemoSession(): Promise<string> {
  const response = await adminRequest<{ access_token: string }>("/api/v1/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ email: "canbo.muong_pon@dienbien.gov.vn", password: "123456" }),
  });
  return response.access_token;
}
