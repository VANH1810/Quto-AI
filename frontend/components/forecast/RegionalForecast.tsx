"use client";

import {
  AlertTriangle,
  Droplets,
  Flashlight,
  Gauge,
  MapPin,
  Mountain,
  ShieldCheck,
  Wind,
  Waves,
} from "lucide-react";
import type { CSSProperties, ComponentType, SVGProps } from "react";
import { useCallback, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { CommuneLocationPicker } from "@/components/CommuneLocationPicker";
import { ForecastDayCard } from "@/components/forecast/ForecastDayCard";
import { IntradayChart } from "@/components/forecast/IntradayChart";
import { useSharedLocation } from "@/contexts/LocationContext";
import { useAlertData } from "@/hooks/useAlertData";
import { useCommuneOverview } from "@/hooks/useCommuneOverview";
import type { ForecastAction } from "@/types/forecast";
import { featureContainsCoordinates } from "@/utils/geo";
import { buildRegionalForecast } from "@/utils/forecast";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

const ACTION_ICONS: Record<ForecastAction["icon"], IconComponent> = {
  light: Flashlight,
  speed: Gauge,
  mountain: Mountain,
  safe: ShieldCheck,
};

export function RegionalForecast() {
  const { data: dashboardData, error: dashboardError, isLoading: isDashboardLoading } = useAlertData();
  const {
    query,
    selectedCommuneCode,
    position,
    locationError,
    isLocating,
    changeQuery,
    selectCommune,
    clearCommune,
    locateCurrentPosition,
  } = useSharedLocation();
  const [selectedDayId, setSelectedDayId] = useState<string | null>(null);

  const gpsCommuneCode = useMemo(() => {
    if (!dashboardData || !position) return null;
    return dashboardData.boundaries.features.find((feature) => featureContainsCoordinates(feature, position))?.properties.code ?? null;
  }, [dashboardData, position]);

  const fallbackCommuneCode = useMemo(() => {
    if (!dashboardData) return null;
    return dashboardData.alerts.reduce((highest, alert) => alert.riskLevel > highest.riskLevel ? alert : highest, dashboardData.alerts[0])?.communeCode
      ?? dashboardData.communeCenters[0]?.code
      ?? null;
  }, [dashboardData]);
  const activeCommuneCode = selectedCommuneCode ?? gpsCommuneCode ?? fallbackCommuneCode;
  const activeCommune = useMemo(
    () => dashboardData?.communeCenters.find((commune) => commune.code === activeCommuneCode) ?? null,
    [activeCommuneCode, dashboardData],
  );
  const currentAlert = useMemo(
    () => dashboardData?.alerts.find((alert) => alert.communeCode === activeCommuneCode),
    [activeCommuneCode, dashboardData],
  );
  const { data: overview, error: forecastError, isLoading: isForecastLoading } = useCommuneOverview(activeCommune, currentAlert);
  const forecastDays = useMemo(
    () => overview ? buildRegionalForecast(overview, currentAlert) : [],
    [currentAlert, overview],
  );
  const selectedDay = useMemo(
    () => forecastDays.find((day) => day.id === selectedDayId) ?? forecastDays[0],
    [forecastDays, selectedDayId],
  );

  const detailStyle = useMemo(() => selectedDay ? ({
    "--forecast-accent": selectedDay.accent,
    "--forecast-tint": selectedDay.tint,
  } as CSSProperties) : undefined, [selectedDay]);

  const handleSelectCommune = useCallback((code: string) => {
    const commune = dashboardData?.communeCenters.find((item) => item.code === code);
    if (commune) selectCommune(commune.code, commune.name);
  }, [dashboardData, selectCommune]);

  const locationLabel = selectedCommuneCode ? "Khu vực đang xem" : gpsCommuneCode ? "Vị trí hiện tại" : "Khu vực ưu tiên";
  const isLoading = isDashboardLoading || isForecastLoading;
  const error = dashboardError ?? forecastError;

  return (
    <main className="app-shell forecast-shell">
      <AppHeader activePage="forecast" />
      <div className="forecast-background">
        <div className="forecast-layout">
          <aside className="forecast-sidebar" aria-labelledby="seven-day-heading">
            {dashboardData && (
              <CommuneLocationPicker
                className="forecast-location-picker"
                communes={dashboardData.communeCenters}
                alerts={dashboardData.alerts}
                query={query}
                isLocating={isLocating}
                locationError={locationError}
                hasUserPosition={Boolean(position)}
                selectedCommuneCode={selectedCommuneCode ?? gpsCommuneCode ?? undefined}
                onQueryChange={changeQuery}
                onSelectCommune={handleSelectCommune}
                onClearCommune={clearCommune}
                onLocate={locateCurrentPosition}
              />
            )}
            <h1 id="seven-day-heading">Dự báo thời tiết 7 ngày</h1>
            <div className="forecast-day-list" role="list" aria-label="Chọn ngày dự báo">
              {forecastDays.map((day) => (
                <div role="listitem" key={day.id}>
                  <ForecastDayCard day={day} isActive={day.id === selectedDay?.id} onSelect={setSelectedDayId} />
                </div>
              ))}
              {isLoading && Array.from({ length: 7 }, (_, index) => <span className="forecast-day-skeleton" key={index} />)}
            </div>
          </aside>

          <section className="forecast-content" aria-live="polite" aria-busy={isLoading} style={detailStyle}>
            {error && (
              <div className="forecast-inline-error" role="alert">
                <AlertTriangle aria-hidden="true" />
                <span><strong>Chưa thể tải dự báo</strong><small>{error}</small></span>
              </div>
            )}
            {!error && selectedDay && overview && (
              <>
                <article className="forecast-glass forecast-overview">
                  <div className="forecast-current">
                    <div className="forecast-location-label"><MapPin aria-hidden="true" /><span>{locationLabel}</span></div>
                    <h2>{selectedDay.location}</h2>
                    <strong className="forecast-main-temperature">{selectedDay.temperature}°C</strong>
                    <p>Min {selectedDay.minTemperature}°C</p>
                    <small className="forecast-source">{overview.forecast_7_days.source}</small>
                  </div>

                  <div className="forecast-detail-column">
                    <div className="forecast-metrics" aria-label="Chỉ số thời tiết">
                      <div className="forecast-metric"><Droplets aria-hidden="true" /><span>Lượng mưa</span><strong>{selectedDay.rainfall}mm</strong></div>
                      <div className="forecast-metric"><Wind aria-hidden="true" /><span>Tốc độ gió</span><strong>{selectedDay.windSpeed}km/h</strong></div>
                      <div className="forecast-metric"><Waves aria-hidden="true" /><span>Độ ẩm</span><strong>{selectedDay.humidity}%</strong></div>
                    </div>

                    <div className="forecast-risk-summary">
                      <div className="forecast-risk-title"><span>Loại rủi ro:</span><strong>{selectedDay.hazardLabel}</strong></div>
                      <div className="forecast-risk-level">
                        <span>Mức độ nguy hiểm:</span>
                        <div className="risk-level-dots" aria-label={`Mức độ nguy hiểm ${selectedDay.riskLevel} trên 5`}>
                          {[1, 2, 3, 4, 5].map((level) => <i className={level <= selectedDay.riskLevel ? "filled" : ""} key={level} />)}
                        </div>
                      </div>
                    </div>
                  </div>
                </article>

                <div className="forecast-lower-grid">
                  <IntradayChart day={selectedDay} />
                  <section className="forecast-glass forecast-actions" aria-labelledby="actions-heading">
                    <h2 id="actions-heading">Hành động cần làm ngay</h2>
                    <ol>
                      {selectedDay.actions.map((action) => {
                        const ActionIcon = ACTION_ICONS[action.icon];
                        return (
                          <li key={action.id}>
                            <span className="forecast-action-icon"><ActionIcon aria-hidden="true" /></span>
                            <span><strong>{action.title}</strong><small>{action.description}</small></span>
                          </li>
                        );
                      })}
                    </ol>
                  </section>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
