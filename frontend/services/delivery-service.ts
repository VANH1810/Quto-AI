import { dataGatewayRequest } from "@/services/dataGatewayClient";
import type { AdminAlert, AuditEntry, DeliveryIncident, Speaker, UnreachedRecipients } from "@/types/admin-console";

export function getDeliveryIncidents(token?: string, signal?: AbortSignal): Promise<DeliveryIncident[]> {
  return dataGatewayRequest("/admin/delivery", token, { signal });
}

export function getAlerts(token?: string, signal?: AbortSignal): Promise<AdminAlert[]> {
  return dataGatewayRequest("/admin/alerts", token, { signal });
}

export function getUnreachedRecipients(alertId: string, token?: string): Promise<UnreachedRecipients> {
  return dataGatewayRequest(`/admin/unreached/${encodeURIComponent(alertId)}`, token);
}

export async function retryAlert(alertId: string, token?: string): Promise<void> {
  await dataGatewayRequest(`/admin/retry/${encodeURIComponent(alertId)}`, token, { method: "POST" });
}

export async function markRecipientContacted(recipientId: string, token?: string): Promise<void> {
  await dataGatewayRequest(`/admin/contacted/${encodeURIComponent(recipientId)}`, token, {
    method: "PATCH",
    body: JSON.stringify({
      status: "home_visit",
      detail: "Cán bộ xác nhận đã liên hệ trực tiếp từ dashboard.",
    }),
  });
}

export function getSpeakers(token?: string): Promise<Speaker[]> {
  return dataGatewayRequest("/admin/speakers", token);
}

export function getAuditEntries(token?: string): Promise<AuditEntry[]> {
  return dataGatewayRequest("/admin/audit", token);
}
