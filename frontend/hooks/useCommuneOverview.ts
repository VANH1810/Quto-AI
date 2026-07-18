"use client";

import { useEffect, useState } from "react";
import { getCommuneOverview } from "@/services/forecastService";
import type { CommuneOverview } from "@/types/forecast";

export function useCommuneOverview(communeCode: string | null) {
  const [data, setData] = useState<CommuneOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(communeCode));

  useEffect(() => {
    let isCurrent = true;
    if (!communeCode) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return () => { isCurrent = false; };
    }

    setData(null);
    setIsLoading(true);
    setError(null);
    getCommuneOverview(communeCode)
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
  }, [communeCode]);

  return { data, error, isLoading };
}
