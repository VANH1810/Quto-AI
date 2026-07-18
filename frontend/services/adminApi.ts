import { adminRequest } from "@/services/adminClient";

export interface AdminIdentity {
  id: string;
  email: string;
  full_name: string;
  role: "village" | "commune" | "province";
  communes: string[];
}

export async function loginAdmin(email: string, password: string): Promise<string> {
  const response = await adminRequest<{ access_token: string }>("/api/v1/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return response.access_token;
}

export function getCurrentAdmin(token: string): Promise<AdminIdentity> {
  return adminRequest<AdminIdentity>("/api/v1/auth/me", token);
}
