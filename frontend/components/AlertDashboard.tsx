"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, LocateFixed, RefreshCw } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { DetailPanel } from "@/components/DetailPanel";
import { MapLegend } from "@/components/MapLegend";
import { SearchSidebar } from "@/components/SearchSidebar";
import { useAlertData } from "@/hooks/useAlertData";
import { useGeolocation } from "@/hooks/useGeolocation";
import type { RiskFilter, SelectedPlace } from "@/types";

const MapCanvas = dynamic(() => import("@/components/MapCanvas"), {
  ssr: false,
  loading: () => <div className="map-loading"><span /><p>Đang tải bản đồ cảnh báo…</p></div>,
});

export function AlertDashboard() {
  const { data, error, isLoading } = useAlertData();
  const { position, error: locationError, isLocating, locate } = useGeolocation();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<RiskFilter>("all");
  const [selection, setSelection] = useState<SelectedPlace | null>({ type: "commune", id: "03202" });

  useEffect(() => {
    if (position) setSelection({ type: "user", id: "current" });
  }, [position]);

  const focusPoint = useMemo<[number, number] | null>(() => {
    if (!data || !selection) return null;
    if (selection.type === "user") return position ? [position.lat, position.lon] : null;
    if (selection.type === "shelter") {
      const shelter = data.shelters.find((item) => item.id === selection.id);
      return shelter ? [shelter.lat, shelter.lon] : null;
    }
    const commune = data.communeCenters.find((item) => item.code === selection.id);
    return commune ? [commune.lat, commune.lon] : null;
  }, [data, position, selection]);

  function selectCommune(code: string) {
    setSelection({ type: "commune", id: code });
  }

  function changeFilter(nextFilter: RiskFilter) {
    setFilter(nextFilter);
    if (nextFilter !== "all" && data) {
      const nextAlert = data.alerts
        .filter((alert) => alert.hazard === nextFilter)
        .sort((a, b) => b.riskLevel - a.riskLevel)[0];
      if (nextAlert) setSelection({ type: "commune", id: nextAlert.communeCode });
    }
  }

  if (isLoading) {
    return <main className="app-shell"><AppHeader /><div className="full-loading"><span /><strong>Đang chuẩn bị bản đồ Điện Biên</strong><p>Tải ranh giới xã và dữ liệu cảnh báo...</p></div></main>;
  }

  if (error || !data) {
    return <main className="app-shell"><AppHeader /><div className="error-state"><AlertTriangle size={34} /><h1>Không thể tải bản đồ</h1><p>{error}</p><button onClick={() => window.location.reload()}><RefreshCw size={17} /> Thử lại</button></div></main>;
  }

  const highRiskCount = data.alerts.filter((alert) => alert.riskLevel >= 4).length;
  return (
    <main className="app-shell">
      <AppHeader />
      <div className="mobile-summary"><span><AlertTriangle size={17} /> {highRiskCount} khu vực nguy cơ cao</span><button onClick={locate}><LocateFixed size={17} /> Định vị</button></div>
      <div className="dashboard-grid">
        <SearchSidebar
          communes={data.communeCenters}
          alerts={data.alerts}
          query={query}
          filter={filter}
          isLocating={isLocating}
          locationError={locationError}
          selectedCommuneCode={selection?.type === "commune" ? selection.id : undefined}
          onQueryChange={setQuery}
          onFilterChange={changeFilter}
          onSelectCommune={selectCommune}
          onLocate={locate}
        />
        <section className="map-panel" aria-label="Bản đồ cảnh báo thời tiết Điện Biên">
          <div className="map-summary"><span><i className="pulse-dot" /> 45 xã/phường · địa giới từ 01/07/2025</span><strong>{highRiskCount} khu vực cần chú ý ngay</strong></div>
          <MapCanvas {...data} filter={filter} selection={selection} userPosition={position} focusPoint={focusPoint} focusZoom={selection?.type === "commune" ? 9 : 12} onSelect={setSelection} />
          <MapLegend />
        </section>
        <DetailPanel selection={selection} alerts={data.alerts} communes={data.communeCenters} shelters={data.shelters} userPosition={position} onSelectShelter={(id) => setSelection({ type: "shelter", id })} />
      </div>
    </main>
  );
}
