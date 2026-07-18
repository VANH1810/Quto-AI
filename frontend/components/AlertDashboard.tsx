"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, LocateFixed, RefreshCw } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { MapLegend } from "@/components/MapLegend";
import { SearchSidebar } from "@/components/SearchSidebar";
import { useSharedLocation } from "@/contexts/LocationContext";
import { useAlertData } from "@/hooks/useAlertData";
import type { Coordinates, RiskFilter, SelectedPlace } from "@/types";
import { featureContainsCoordinates, representativePointFromFeature } from "@/utils/geo";

const MapCanvas = dynamic(() => import("@/components/MapCanvas"), {
  ssr: false,
  loading: () => <div className="map-loading"><span /><p>Đang tải bản đồ cảnh báo…</p></div>,
});
const DetailPanel = dynamic(
  () => import("@/components/DetailPanel").then((module) => module.DetailPanel),
  { ssr: false },
);

const USER_SELECTION: SelectedPlace = { type: "user", id: "current" };

export function AlertDashboard() {
  const { data, error, isLoading } = useAlertData();
  const {
    position,
    locationError,
    isLocating,
    query,
    selectedCommuneCode,
    changeQuery: changeSharedQuery,
    selectCommune: selectSharedCommune,
    clearCommune: clearSharedCommune,
    locateCurrentPosition: locateSharedPosition,
  } = useSharedLocation();
  const [filter, setFilter] = useState<RiskFilter>("all");
  const [selection, setSelection] = useState<SelectedPlace | null>(null);
  const hasDetailSelection = selection?.type === "commune" || selection?.type === "shelter";
  const [isDetailColumnVisible, setIsDetailColumnVisible] = useState(hasDetailSelection);

  useEffect(() => {
    if (selectedCommuneCode) {
      setSelection((current) => current?.type === "commune" && current.id === selectedCommuneCode
        ? current
        : { type: "commune", id: selectedCommuneCode });
    } else if (position) {
      setSelection(USER_SELECTION);
    }
  }, [position, selectedCommuneCode]);

  useEffect(() => {
    if (hasDetailSelection) {
      setIsDetailColumnVisible(true);
      return;
    }

    const timeout = window.setTimeout(() => setIsDetailColumnVisible(false), 300);
    return () => window.clearTimeout(timeout);
  }, [hasDetailSelection]);

  const gpsCommuneCode = useMemo(() => {
    if (!data || !position) return null;
    return data.boundaries.features.find((feature) => featureContainsCoordinates(feature, position))?.properties.code ?? null;
  }, [data, position]);

  const activeCommuneCode = selectedCommuneCode ?? gpsCommuneCode;
  const visibleShelters = useMemo(
    () => data && activeCommuneCode
      ? data.shelters.filter((shelter) => shelter.communeCode === activeCommuneCode)
      : [],
    [activeCommuneCode, data],
  );

  const routeOrigin = useMemo<Coordinates | null>(() => {
    if (position) return position;
    if (!data || !selectedCommuneCode) return null;
    const feature = data.boundaries.features.find((item) => item.properties.code === selectedCommuneCode);
    return feature ? representativePointFromFeature(feature) : null;
  }, [data, position, selectedCommuneCode]);

  const resetToUserPosition = useCallback(() => {
    setSelection((current) => {
      if (position) return current?.type === "user" ? current : USER_SELECTION;
      return current === null ? current : null;
    });
  }, [position]);

  const clearCommune = useCallback(() => {
    clearSharedCommune();
    resetToUserPosition();
  }, [clearSharedCommune, resetToUserPosition]);

  const locateCurrentPosition = useCallback(() => {
    resetToUserPosition();
    locateSharedPosition();
  }, [locateSharedPosition, resetToUserPosition]);

  const selectMapPlace = useCallback((place: SelectedPlace) => {
    if (place.type === "commune") {
      const commune = data?.communeCenters.find((item) => item.code === place.id);
      if (commune) selectSharedCommune(commune.code, commune.name);
    }
    setSelection(place);
  }, [data, selectSharedCommune]);

  const changeFilter = useCallback((nextFilter: RiskFilter) => {
    setFilter(nextFilter);
  }, []);

  const closeDetailPanel = useCallback(() => {
    resetToUserPosition();
  }, [resetToUserPosition]);

  const changeQuery = useCallback((value: string) => {
    changeSharedQuery(value);
    resetToUserPosition();
  }, [changeSharedQuery, resetToUserPosition]);

  const selectSidebarCommune = useCallback((code: string) => {
    const commune = data?.communeCenters.find((item) => item.code === code);
    if (commune) selectSharedCommune(commune.code, commune.name);
    setSelection({ type: "commune", id: code });
  }, [data, selectSharedCommune]);

  const selectShelter = useCallback((id: string) => {
    setSelection({ type: "shelter", id });
  }, []);

  const highRiskCount = useMemo(
    () => data?.alerts.filter((alert) => alert.riskLevel >= 4).length ?? 0,
    [data],
  );

  if (isLoading) {
    return <main className="app-shell"><AppHeader /><div className="full-loading"><span /><strong>Đang chuẩn bị bản đồ Điện Biên</strong><p>Tải ranh giới xã và dữ liệu cảnh báo...</p></div></main>;
  }

  if (error || !data) {
    return <main className="app-shell"><AppHeader /><div className="error-state"><AlertTriangle size={34} /><h1>Không thể tải bản đồ</h1><p>{error}</p><button onClick={() => window.location.reload()}><RefreshCw size={17} /> Thử lại</button></div></main>;
  }

  return (
    <main className="app-shell">
      <AppHeader />
      <div className="mobile-summary"><span><AlertTriangle size={17} /> {highRiskCount} khu vực nguy cơ cao</span><button onClick={locateCurrentPosition}><LocateFixed size={17} /> Định vị</button></div>
      <div className={`dashboard-grid${isDetailColumnVisible ? " detail-visible" : ""}`}>
        <section className="map-panel" aria-label="Bản đồ cảnh báo thời tiết Điện Biên">
          <SearchSidebar
            communes={data.communeCenters}
            alerts={data.alerts}
            query={query}
            filter={filter}
            isLocating={isLocating}
            locationError={locationError}
            hasUserPosition={Boolean(position)}
            selectedCommuneCode={selectedCommuneCode ?? undefined}
            onQueryChange={changeQuery}
            onFilterChange={changeFilter}
            onSelectCommune={selectSidebarCommune}
            onClearCommune={clearCommune}
            onLocate={locateCurrentPosition}
          />
          <div className="map-summary"><span><i className="pulse-dot" /> 45 xã/phường · địa giới từ 01/07/2025</span><strong>{highRiskCount} khu vực cần chú ý ngay</strong></div>
          <MapCanvas {...data} shelters={visibleShelters} filter={filter} selection={selection} userPosition={position} routeOrigin={routeOrigin} onSelect={selectMapPlace} />
          <MapLegend />
        </section>
        {isDetailColumnVisible && <DetailPanel selection={selection} alerts={data.alerts} communes={data.communeCenters} shelters={visibleShelters} routeOrigin={routeOrigin} onSelectShelter={selectShelter} onClose={closeDetailPanel} />}
      </div>
    </main>
  );
}
