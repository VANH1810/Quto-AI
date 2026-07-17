import { adminCommunesMock } from "@/mocks/admin-scope.mock";
import { adminRequest, useMocks } from "@/services/adminClient";
import type { AdminCommune } from "@/types/admin-console";
export async function getAdminCommunes(token?: string): Promise<AdminCommune[]> { if (useMocks) return adminCommunesMock; return (await adminRequest<{ data: AdminCommune[] }>("/api/v1/admin/me/communes", token)).data; }
