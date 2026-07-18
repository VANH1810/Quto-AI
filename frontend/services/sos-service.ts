import { dataGatewayRequest } from "@/services/dataGatewayClient";
import type { SOSRequest, SOSStatus, SOSSubmission, SOSSubmissionResult } from "@/types/sos";

export function getSos(token?: string, signal?: AbortSignal): Promise<SOSRequest[]> {
  return dataGatewayRequest("/admin/sos", token, { signal });
}

export function getSosDetail(id: string, token?: string): Promise<SOSRequest | undefined> {
  return dataGatewayRequest(`/admin/sos/${encodeURIComponent(id)}`, token);
}

export async function updateSosStatus(id: string, status: SOSStatus, token?: string): Promise<void> {
  await dataGatewayRequest(`/admin/sos/${encodeURIComponent(id)}`, token, {
    method: "PATCH",
    body: JSON.stringify({ status: status.toLowerCase() }),
  });
}

export async function submitSos(payload: SOSSubmission, deviceId: string): Promise<SOSSubmissionResult> {
  const result = await dataGatewayRequest<SOSSubmissionResult>("/sos", undefined, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "X-Device-ID": deviceId },
  });
  if (!result?.id || !result.status || !result.created_at) {
    throw new Error("API cứu hộ chưa xác nhận mã tín hiệu SOS.");
  }
  return result;
}

export function createGoogleMapsDirectionsUrl(latitude: number, longitude: number) {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${latitude},${longitude}`)}&dir_action=navigate`;
}
