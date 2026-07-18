"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useGeolocation } from "@/hooks/useGeolocation";
import type { UserPosition } from "@/types";

interface LocationContextValue {
  query: string;
  selectedCommuneCode: string | null;
  position: UserPosition | null;
  locationError: string | null;
  isLocating: boolean;
  changeQuery: (value: string) => void;
  selectCommune: (code: string, name: string) => void;
  clearCommune: () => void;
  locateCurrentPosition: () => void;
}

const LocationContext = createContext<LocationContextValue | null>(null);

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const { position, error: locationError, isLocating, locate } = useGeolocation();
  const [query, setQuery] = useState("");
  const [selectedCommuneCode, setSelectedCommuneCode] = useState<string | null>(null);

  const changeQuery = useCallback((value: string) => {
    setQuery(value);
    setSelectedCommuneCode(null);
  }, []);

  const selectCommune = useCallback((code: string, name: string) => {
    setQuery(name);
    setSelectedCommuneCode(code);
  }, []);

  const clearCommune = useCallback(() => {
    setQuery("");
    setSelectedCommuneCode(null);
  }, []);

  const locateCurrentPosition = useCallback(() => {
    setQuery("");
    setSelectedCommuneCode(null);
    locate();
  }, [locate]);

  const value = useMemo(() => ({
    query,
    selectedCommuneCode,
    position,
    locationError,
    isLocating,
    changeQuery,
    selectCommune,
    clearCommune,
    locateCurrentPosition,
  }), [changeQuery, clearCommune, isLocating, locateCurrentPosition, locationError, position, query, selectCommune, selectedCommuneCode]);

  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useSharedLocation() {
  const context = useContext(LocationContext);
  if (!context) throw new Error("useSharedLocation must be used inside LocationProvider");
  return context;
}
