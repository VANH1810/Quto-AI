"use client";

import Image from "next/image";
import { memo } from "react";
import { CommuneLocationPicker } from "@/components/CommuneLocationPicker";
import type { CommuneAlert, CommuneCenter, HazardType, RiskFilter } from "@/types";
import { HAZARD_META } from "@/utils/risk";

const filterIcons = {
  flash_flood: "/figma/flash-flood.svg",
  landslide: "/figma/landslide.svg",
  heavy_rain: "/figma/heavy-rain.svg",
  frost: "/figma/frost.svg",
  fog: "/figma/fog.png",
};

interface SearchSidebarProps {
  communes: CommuneCenter[];
  alerts: CommuneAlert[];
  query: string;
  filter: RiskFilter;
  isLocating: boolean;
  locationError: string | null;
  hasUserPosition: boolean;
  selectedCommuneCode?: string;
  onQueryChange: (value: string) => void;
  onFilterChange: (filter: RiskFilter) => void;
  onSelectCommune: (code: string) => void;
  onClearCommune: () => void;
  onLocate: () => void;
}

export const SearchSidebar = memo(function SearchSidebar(props: SearchSidebarProps) {
  return (
    <aside className="search-sidebar" aria-label="Chọn xã phường và bộ lọc">
      <section className="sidebar-section search-section">
        <CommuneLocationPicker
          communes={props.communes}
          alerts={props.alerts}
          query={props.query}
          isLocating={props.isLocating}
          locationError={props.locationError}
          hasUserPosition={props.hasUserPosition}
          selectedCommuneCode={props.selectedCommuneCode}
          onQueryChange={props.onQueryChange}
          onSelectCommune={props.onSelectCommune}
          onClearCommune={props.onClearCommune}
          onLocate={props.onLocate}
        />
      </section>

      <section className="sidebar-section filter-section">
        <div className="section-heading"><span>Loại rủi ro</span><small>{props.filter === "all" ? "Tất cả" : HAZARD_META[props.filter].label}</small></div>
        <div className="risk-filters">
          <button className={props.filter === "all" ? "active" : ""} onClick={() => props.onFilterChange("all")}><span className="all-filter-icon">5</span>Tất cả</button>
          {(Object.keys(filterIcons) as HazardType[]).map((hazard) => (
            <button key={hazard} className={props.filter === hazard ? "active" : ""} onClick={() => props.onFilterChange(hazard)}>
              <Image src={filterIcons[hazard]} width={28} height={28} alt="" aria-hidden="true" />{HAZARD_META[hazard].label}
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
});
