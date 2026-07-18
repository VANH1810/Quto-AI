"use client";

import { useEffect, useState } from "react";
import { getCommuneOverview } from "@/services/forecastService";
import type { CommuneAlert, CommuneCenter } from "@/types";
import type { CommuneOverview } from "@/types/forecast";

export function useCommuneOverview(commune: CommuneCenter | null, alert?: CommuneAlert) {
  const [data, setData] = useState<CommuneOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(commune));

  useEffect(() => {
    let isCurrent = true;
    if (!commune) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return () => { isCurrent = false; };
    }

    setData(null);
    setIsLoading(true);
    setError(null);
    getCommuneOverview(commune, alert)
      .then((overview) => {
        if (isCurrent) setData(overview);
      })
      .catch((reason: unknown) => {
        if (isCurrent) {
          setData(null);
          setError(reason instanceof Error ? reason.message : "Không thể tải dự báo khu vực.");
        }
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => { isCurrent = false; };
  }, [alert, commune]);

  return { data, error, isLoading };
}
