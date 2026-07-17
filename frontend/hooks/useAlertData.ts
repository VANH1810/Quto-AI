"use client";

import { useEffect, useState } from "react";
import { alertService } from "@/services/alertService";
import type { DashboardData } from "@/types";

export function useAlertData() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    alertService.getDashboardData()
      .then((result) => active && setData(result))
      .catch((reason: unknown) => active && setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu"))
      .finally(() => active && setIsLoading(false));
    return () => { active = false; };
  }, []);

  return { data, error, isLoading };
}
