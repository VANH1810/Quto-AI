import type { DashboardData } from "@/types";

export interface AlertDataSource {
  getDashboardData(signal?: AbortSignal): Promise<DashboardData>;
}

class ServerAlertDataSource implements AlertDataSource {
  async getDashboardData(signal?: AbortSignal): Promise<DashboardData> {
    const response = await fetch("/api/data/dashboard", { signal });
    const payload = await response.json().catch(() => null) as
      | { data?: DashboardData; error?: string }
      | null;

    if (!response.ok || !payload?.data) {
      throw new Error(payload?.error ?? "Không thể tải dữ liệu cảnh báo.");
    }
    return payload.data;
  }
}

export function createAlertDataSource(): AlertDataSource {
  return new ServerAlertDataSource();
}
