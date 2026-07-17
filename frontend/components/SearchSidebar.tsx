"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import { ChevronDown, LocateFixed, MapPinned } from "lucide-react";
import type { CommuneAlert, CommuneCenter, HazardType, RiskFilter } from "@/types";
import { HAZARD_META, RISK_META } from "@/utils/risk";

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

export function SearchSidebar(props: SearchSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const normalized = props.query.trim().toLocaleLowerCase("vi");
  const alertsByCommune = useMemo(() => new Map(props.alerts.map((alert) => [alert.communeCode, alert])), [props.alerts]);
  const selectedCommune = props.communes.find((commune) => commune.code === props.selectedCommuneCode);
  const selectedNameIsShown = selectedCommune?.name === props.query;
  const visibleCommunes = selectedNameIsShown
    ? props.communes
    : props.communes.filter((commune) =>
        !normalized || `${commune.name} ${commune.district}`.toLocaleLowerCase("vi").includes(normalized),
      );

  function selectCommune(commune: CommuneCenter) {
    props.onSelectCommune(commune.code);
    setIsOpen(false);
    setActiveIndex(0);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => Math.min(index + 1, Math.max(visibleCommunes.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && isOpen && visibleCommunes[activeIndex]) {
      event.preventDefault();
      selectCommune(visibleCommunes[activeIndex]);
    } else if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  return (
    <aside className="search-sidebar" aria-label="Chọn xã phường và bộ lọc">
      <section className="sidebar-section search-section">
        <div className="commune-combobox">
          <span className="field-label">Vị trí tại Điện Biên</span>
          <div className={isOpen ? "search-box open" : "search-box"}>
            <Image className="figma-search-icon" src="/figma/search.svg" width={25} height={25} alt="" aria-hidden="true" />
            <input
              role="combobox"
              aria-label="Chọn xã hoặc phường"
              aria-autocomplete="list"
              aria-expanded={isOpen}
              aria-controls="commune-options"
              aria-activedescendant={isOpen && visibleCommunes[activeIndex] ? `commune-${visibleCommunes[activeIndex].code}` : undefined}
              value={props.query}
              onFocus={() => setIsOpen(true)}
              onBlur={() => window.setTimeout(() => setIsOpen(false), 0)}
              onChange={(event) => {
                props.onQueryChange(event.target.value);
                setActiveIndex(0);
                setIsOpen(true);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Nhập để chọn xã/phường..."
            />
            {props.query ? (
              <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => { props.onClearCommune(); setIsOpen(true); }} aria-label="Xóa xã phường đã chọn">×</button>
            ) : (
              <button type="button" className="dropdown-toggle" onMouseDown={(event) => event.preventDefault()} onClick={() => setIsOpen((open) => !open)} aria-label="Mở danh sách xã phường"><ChevronDown size={17} /></button>
            )}
          </div>

          {isOpen && (
            <div id="commune-options" className="commune-options" role="listbox" aria-label="Danh sách xã phường Điện Biên">
              <div className="commune-options-meta"><span>{visibleCommunes.length} xã/phường</span><small>Gõ tên để lọc</small></div>
              {visibleCommunes.map((commune, index) => {
                const alert = alertsByCommune.get(commune.code);
                if (!alert) return null;
                const risk = RISK_META[alert.riskLevel];
                const selected = commune.code === props.selectedCommuneCode;
                return (
                  <button
                    type="button"
                    id={`commune-${commune.code}`}
                    role="option"
                    aria-selected={selected}
                    key={commune.code}
                    className={`${selected ? "selected " : ""}${index === activeIndex ? "active" : ""}`.trim()}
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => selectCommune(commune)}
                  >
                    <span className="option-risk" style={{ background: risk.color }} />
                    <span className="option-copy"><strong>{commune.name}</strong><small>{alert.hazardLabel}</small></span>
                    <span className="risk-pill" style={{ color: risk.color, background: `${risk.color}18` }}>Cấp {alert.riskLevel}</span>
                  </button>
                );
              })}
              {!visibleCommunes.length && <p className="empty-list">Không tìm thấy xã/phường phù hợp.</p>}
            </div>
          )}

          {selectedCommune && !props.hasUserPosition && (
            <p className="approximate-location"><MapPinned size={15} /><span><strong>Vị trí gần đúng</strong>Đang dùng {selectedCommune.name} để hiển thị khu vực của bạn.</span></p>
          )}
        </div>

        <button className="locate-button" onClick={props.onLocate} disabled={props.isLocating}>
          <LocateFixed size={18} className={props.isLocating ? "spin" : ""} />
          <span>{props.isLocating ? "Đang xác định vị trí..." : props.hasUserPosition ? "Đã dùng vị trí chính xác" : "Dùng vị trí hiện tại của tôi"}</span>
        </button>
        {props.locationError && <p className="inline-error">{props.locationError} Bạn có thể chọn xã/phường ở phía trên.</p>}
      </section>

      <section className="sidebar-section filter-section">
        <div className="section-heading"><span>Loại rủi ro</span><small>{props.filter === "all" ? "Tất cả" : HAZARD_META[props.filter].label}</small></div>
        <div className="risk-filters">
          <button className={props.filter === "all" ? "active" : ""} onClick={() => props.onFilterChange("all")}><span className="all-filter-icon">5</span>Tất cả</button>
          {(Object.keys(filterIcons) as HazardType[]).map((hazard) => {
            return <button key={hazard} className={props.filter === hazard ? "active" : ""} onClick={() => props.onFilterChange(hazard)}><Image src={filterIcons[hazard]} width={28} height={28} alt="" aria-hidden="true" />{HAZARD_META[hazard].label}</button>;
          })}
        </div>
      </section>
    </aside>
  );
}
