"use client";

import { useCallback, useState } from "react";
import type { UserPosition } from "@/types";

export function useGeolocation() {
  const [position, setPosition] = useState<UserPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState(false);

  const locate = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setError("Thiết bị không hỗ trợ định vị.");
      return;
    }
    setIsLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setPosition({ lat: coords.latitude, lon: coords.longitude, accuracy: coords.accuracy });
        setIsLocating(false);
      },
      (reason) => {
        setError(reason.code === reason.PERMISSION_DENIED ? "Bạn chưa cho phép truy cập vị trí." : "Không thể lấy vị trí hiện tại.");
        setIsLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }, []);

  return { position, error, isLocating, locate };
}
