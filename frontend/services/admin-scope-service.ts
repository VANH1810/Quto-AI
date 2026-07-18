import { dataGatewayRequest } from "@/services/dataGatewayClient";
import type { AdminCommune } from "@/types/admin-console";

export function getAdminCommunes(token?: string, signal?: AbortSignal): Promise<AdminCommune[]> {
  return dataGatewayRequest("/admin/communes", token, { signal });
}
