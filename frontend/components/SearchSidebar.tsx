import { CloudFog, CloudRain, LocateFixed, MapPin, Mountain, Search, Snowflake, Waves } from "lucide-react";
import type { CommuneAlert, CommuneCenter, HazardType, RiskFilter } from "@/types";
import { HAZARD_META, RISK_META } from "@/utils/risk";

const filterIcons = {
  flash_flood: Waves,
  landslide: Mountain,
  heavy_rain: CloudRain,
  frost: Snowflake,
  fog: CloudFog,
};

interface SearchSidebarProps {
  communes: CommuneCenter[];
  alerts: CommuneAlert[];
  query: string;
  filter: RiskFilter;
  isLocating: boolean;
  locationError: string | null;
  selectedCommuneCode?: string;
  onQueryChange: (value: string) => void;
  onFilterChange: (filter: RiskFilter) => void;
  onSelectCommune: (code: string) => void;
  onLocate: () => void;
}

export function SearchSidebar(props: SearchSidebarProps) {
  const normalized = props.query.trim().toLocaleLowerCase("vi");
  const visibleCommunes = props.communes.filter((commune) => {
    const alert = props.alerts.find((item) => item.communeCode === commune.code);
    const matchesQuery = !normalized || `${commune.name} ${commune.district}`.toLocaleLowerCase("vi").includes(normalized);
    const matchesFilter = props.filter === "all" || alert?.hazard === props.filter;
    return matchesQuery && matchesFilter;
  });

  return (
    <aside className="search-sidebar" aria-label="Tìm kiếm và bộ lọc">
      <section className="sidebar-section search-section">
        <label className="search-box">
          <Search size={18} />
          <input value={props.query} onChange={(event) => props.onQueryChange(event.target.value)} placeholder="Tìm xã, thị trấn..." aria-label="Tìm xã" />
          {props.query && <button onClick={() => props.onQueryChange("")} aria-label="Xóa tìm kiếm">×</button>}
        </label>
        <button className="locate-button" onClick={props.onLocate} disabled={props.isLocating}>
          <LocateFixed size={18} className={props.isLocating ? "spin" : ""} />
          {props.isLocating ? "Đang xác định vị trí..." : "Định vị vị trí của tôi"}
        </button>
        {props.locationError && <p className="inline-error">{props.locationError}</p>}
      </section>

      <section className="sidebar-section filter-section">
        <div className="section-heading"><span>Loại rủi ro</span><small>{props.filter === "all" ? "Tất cả" : HAZARD_META[props.filter].label}</small></div>
        <div className="risk-filters">
          <button className={props.filter === "all" ? "active" : ""} onClick={() => props.onFilterChange("all")}><span className="all-filter-icon">5</span>Tất cả</button>
          {(Object.keys(filterIcons) as HazardType[]).map((hazard) => {
            const Icon = filterIcons[hazard];
            return <button key={hazard} className={props.filter === hazard ? "active" : ""} onClick={() => props.onFilterChange(hazard)}><Icon size={17} />{HAZARD_META[hazard].label}</button>;
          })}
        </div>
      </section>

      <section className="sidebar-section commune-section">
        <div className="section-heading"><span>Khu vực theo dõi</span><small>{visibleCommunes.length} khu vực</small></div>
        <div className="commune-list">
          {visibleCommunes.map((commune) => {
            const alert = props.alerts.find((item) => item.communeCode === commune.code);
            if (!alert) return null;
            const risk = RISK_META[alert.riskLevel];
            return (
              <button key={commune.code} className={props.selectedCommuneCode === commune.code ? "commune-card active" : "commune-card"} onClick={() => props.onSelectCommune(commune.code)}>
                <span className="commune-pin" style={{ background: risk.color }}><MapPin size={15} /></span>
                <span className="commune-copy"><strong>{commune.name}</strong><small>{alert.hazardLabel}</small></span>
                <span className="risk-pill" style={{ color: risk.color, background: `${risk.color}18` }}>Cấp {alert.riskLevel}</span>
              </button>
            );
          })}
          {!visibleCommunes.length && <p className="empty-list">Không tìm thấy khu vực phù hợp.</p>}
        </div>
      </section>
    </aside>
  );
}
