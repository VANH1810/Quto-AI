import { risksMock } from "@/mocks/risks.mock";
import { adminRequest, useMocks } from "@/services/adminClient";
import type { CommuneRisk } from "@/types/admin-console";
export async function getScopedRisks(token?: string): Promise<CommuneRisk[]> { if (useMocks) return risksMock; return (await adminRequest<{ data: { items: CommuneRisk[] } }>("/api/v1/admin/commune-risks", token)).data.items; }
