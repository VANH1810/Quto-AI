import { dataGatewayRequest } from "@/services/dataGatewayClient";
import type { CommuneRisk } from "@/types/admin-console";

export function getScopedRisks(token?: string, signal?: AbortSignal): Promise<CommuneRisk[]> {
  return dataGatewayRequest("/admin/risks", token, { signal });
}
