"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { UserPosition } from "@/types";

export type GeolocationStatus = "idle" | "locating" | "located";

interface UseGeolocationOptions {
  mockPosition: UserPosition;
  autoLocate?: boolean;
}

export function useGeolocation({ mockPosition, autoLocate = false }: UseGeolocationOptions) {
  const [position, setPosition] = useState<UserPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [status, setStatus] = useState<GeolocationStatus>("idle");
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestIdRef.current += 1;
    };
  }, []);

  const locate = useCallback(() => {
    const requestId = ++requestIdRef.current;
    setIsLocating(true);
    setStatus("locating");
    setError(null);
    window.setTimeout(() => {
      if (!mountedRef.current || requestId !== requestIdRef.current) return;
      setPosition(mockPosition);
      setStatus("located");
      setIsLocating(false);
    }, 0);
  }, [mockPosition]);

  useEffect(() => {
    if (!autoLocate) return;
    locate();
  }, [autoLocate, locate]);

  return { position, error, isLocating, status, locate };
}
