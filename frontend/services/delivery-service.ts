import { alertsMock, auditMock, deliveryIncidentsMock, speakersMock, unreachedByAlertMock } from "@/mocks/delivery-incidents.mock";
import { adminRequest, useMocks } from "@/services/adminClient";
import type { AdminAlert, AuditEntry, DeliveryIncident, Speaker, UnreachedRecipients } from "@/types/admin-console";
export async function getDeliveryIncidents(token?: string): Promise<DeliveryIncident[]> { if (useMocks) return deliveryIncidentsMock; return (await adminRequest<{ data: { items: DeliveryIncident[] } }>("/api/v1/admin/delivery-incidents?status=pending", token)).data.items; }
export async function getAlerts(token?: string): Promise<AdminAlert[]> { if (useMocks) return alertsMock; return adminRequest<AdminAlert[]>("/api/v1/alerts", token); }
export async function getUnreachedRecipients(alertId: string, token?: string): Promise<UnreachedRecipients> { if (useMocks) return unreachedByAlertMock[alertId] ?? { alertId, targetedCount: 0, deliveredCount: 0, unreachedCount: 0, recipients: [] }; return (await adminRequest<{ data: UnreachedRecipients }>(`/api/v1/admin/alerts/${alertId}/unreached-recipients`, token)).data; }
export async function retryAlert(alertId: string, token?: string): Promise<void> { if (useMocks) return; await adminRequest(`/api/v1/alerts/${alertId}/retry`, token, { method: "POST" }); }
export async function markRecipientContacted(recipientId: string, token?: string): Promise<void> { if (useMocks) return; await adminRequest(`/api/v1/notifications/${recipientId}`, token, { method: "PATCH", body: JSON.stringify({ status: "home_visit", detail: "Cán bộ xác nhận đã liên hệ trực tiếp từ dashboard." }) }); }
export async function getSpeakers(): Promise<Speaker[]> { return useMocks ? speakersMock : []; }
export async function getAuditEntries(): Promise<AuditEntry[]> { return useMocks ? auditMock : []; }
