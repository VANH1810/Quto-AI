"use client";

import { useEffect, useState } from "react";
import { alertService } from "@/services/alertService";
import type { DashboardData } from "@/types";

let cachedDashboardData: DashboardData | null = null;
let dashboardRequest: Promise<DashboardData> | null = null;

function loadDashboardData() {
  if (cachedDashboardData) return Promise.resolve(cachedDashboardData);
  if (dashboardRequest) return dashboardRequest;

  dashboardRequest = alertService.getDashboardData()
    .then((data) => {
      cachedDashboardData = data;
      return data;
    })
    .finally(() => {
      dashboardRequest = null;
    });
  return dashboardRequest;
}

export function useAlertData() {
  const [data, setData] = useState<DashboardData | null>(cachedDashboardData);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(!cachedDashboardData);

  useEffect(() => {
    let isCurrent = true;
    loadDashboardData()
      .then((nextData) => {
        if (isCurrent) {
          setData(nextData);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (isCurrent) setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => { isCurrent = false; };
  }, []);

  return { data, error, isLoading };
}
