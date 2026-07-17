"use client";

import { useEffect, useState, type CSSProperties } from "react";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock3,
  CloudFog,
  CloudRain,
  MapPinned,
  Mountain,
  Navigation,
  PhoneCall,
  ShieldAlert,
  Snowflake,
  Users,
  Waves,
  X,
  type LucideIcon,
} from "lucide-react";
import type { CommuneAlert, CommuneCenter, Coordinates, HazardType, SelectedPlace, Shelter, UserPosition } from "@/types";
import { googleMapsDirectionsUrl } from "@/utils/directions";
import { RISK_META } from "@/utils/risk";
import { SHELTER_KIND_LABELS } from "@/utils/shelter";

interface DetailPanelProps {
  selection: SelectedPlace | null;
  alerts: CommuneAlert[];
  communes: CommuneCenter[];
  shelters: Shelter[];
  userPosition: UserPosition | null;
  routeOrigin: Coordinates | null;
  onSelectShelter: (id: string) => void;
  onClose: () => void;
}

type DetailPanelStyle = CSSProperties & {
  "--detail-accent"?: string;
};

const DETAIL_PANEL_TRANSITION_MS = 300;

const HAZARD_ICONS: Record<HazardType, LucideIcon> = {
  flash_flood: Waves,
  landslide: Mountain,
  heavy_rain: CloudRain,
  frost: Snowflake,
  fog: CloudFog,
};

export function DetailPanel({ selection, alerts, communes, shelters, routeOrigin, onSelectShelter, onClose }: DetailPanelProps) {
  const visibleSelection = selection?.type === "commune" || selection?.type === "shelter" ? selection : null;
  const [renderedSelection, setRenderedSelection] = useState<SelectedPlace | null>(visibleSelection);
  const [isOpen, setIsOpen] = useState(Boolean(visibleSelection));

  useEffect(() => {
    if (visibleSelection) {
      setRenderedSelection(visibleSelection);
      const frame = window.requestAnimationFrame(() => setIsOpen(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsOpen(false);
    const timeout = window.setTimeout(() => setRenderedSelection(null), DETAIL_PANEL_TRANSITION_MS);
    return () => window.clearTimeout(timeout);
  }, [visibleSelection]);

  if (!renderedSelection) return null;

  const selectedAlert = renderedSelection.type === "commune"
    ? alerts.find((alert) => alert.communeCode === renderedSelection.id)
    : undefined;
  const selectedCommune = selectedAlert
    ? communes.find((item) => item.code === selectedAlert.communeCode)
    : undefined;
  const selectedShelter = renderedSelection.type === "shelter"
    ? shelters.find((item) => item.id === renderedSelection.id)
    : undefined;
  const panelClassName = `detail-panel ${isOpen ? "is-open" : "is-closing"}`;

  if (selectedShelter) {
    const alert = alerts.find((item) => item.communeCode === selectedShelter.communeCode);
    const risk = alert ? RISK_META[alert.riskLevel] : RISK_META[1];
    const ShelterHazardIcon = alert ? HAZARD_ICONS[alert.hazard] : ShieldAlert;

    return (
      <aside className={panelClassName} aria-hidden={!isOpen} inert={isOpen ? undefined : true}>
        <div className="detail-top shelter">
          <span className="detail-icon"><Building2 size={21} /></span>
          <div className="detail-heading">
            <small>Điểm trú ẩn</small>
            <h2>{selectedShelter.name}</h2>
          </div>
          <button type="button" className="detail-close" onClick={onClose} aria-label="Đóng bảng chi tiết"><X size={20} /></button>
        </div>
        <div className="detail-body">
          <div className="shelter-facts">
            <span><MapPinned size={18} /><b>Địa chỉ</b><small>{selectedShelter.address}</small></span>
            <span><Building2 size={18} /><b>Loại địa điểm</b><small>{SHELTER_KIND_LABELS[selectedShelter.kind]}</small></span>
            <span><Users size={18} /><b>Sức chứa dự kiến</b><small>{selectedShelter.capacity ? `${selectedShelter.capacity} người` : "Chưa có dữ liệu xác minh"}</small></span>
            <span><Navigation size={18} /><b>Tọa độ đích</b><small>{selectedShelter.lat}, {selectedShelter.lon}</small></span>
          </div>
          <div className="current-risk" style={{ "--detail-accent": risk.color } as DetailPanelStyle}>
            <span>Nguy cơ tại khu vực</span>
            <strong><ShelterHazardIcon size={18} /> Cấp {alert?.riskLevel ?? 1} · {alert?.hazardLabel ?? "Đang theo dõi"}</strong>
          </div>
          <a className="primary-action" href={googleMapsDirectionsUrl(selectedShelter, routeOrigin)} target="_blank" rel="noopener noreferrer"><Navigation size={18} /> Xem đường đi đến điểm trú ẩn</a>
          <button className="secondary-action"><PhoneCall size={17} /> Gọi ban chỉ huy xã</button>
        </div>
      </aside>
    );
  }

  if (!selectedAlert || !selectedCommune) return null;

  const risk = RISK_META[selectedAlert.riskLevel];
  const HazardIcon = HAZARD_ICONS[selectedAlert.hazard];
  const communeShelters = shelters.filter((item) => item.communeCode === selectedAlert.communeCode);
  const showUpdatedAt = !selectedAlert.updatedAt.toLocaleLowerCase("vi-VN").includes("dữ liệu mô phỏng");
  const panelStyle = {
    "--detail-accent": risk.color,
  } as DetailPanelStyle;

  return (
    <aside className={panelClassName} style={panelStyle} aria-hidden={!isOpen} inert={isOpen ? undefined : true}>
      <div className="detail-top alert-detail-top">
        <div className="detail-heading">
          <small>Khu vực cảnh báo</small>
          <h2>{selectedCommune.name}</h2>
        </div>
        <button type="button" className="detail-close" onClick={onClose} aria-label="Đóng bảng chi tiết"><X size={20} /></button>
        <div className="alert-level-row">
          <span className="detail-icon"><HazardIcon size={23} strokeWidth={2} /></span>
          <span><strong>Cấp {selectedAlert.riskLevel}</strong><small>{risk.shortLabel}</small></span>
        </div>
        <div className="hazard-badge"><HazardIcon size={16} strokeWidth={2} /> {selectedAlert.hazardLabel}</div>
      </div>
      <div className="detail-body alert-detail-body">
        <h3>{selectedAlert.headline}</h3>
        {showUpdatedAt && <div className="alert-updated"><Clock3 size={16} /> {selectedAlert.updatedAt}</div>}
        <p className="detail-description">{selectedAlert.detail}</p>
        <div className="action-card">
          <strong>Việc cần làm ngay</strong>
          {selectedAlert.recommendedActions.map((action) => <p key={action}><CheckCircle2 size={17} />{action}</p>)}
        </div>
        <div className="shelter-count" aria-label={`${communeShelters.length} điểm trú ẩn trong khu vực`}>
          <span className="shelter-count-icon"><Building2 size={19} /></span>
          <span className="shelter-count-copy"><small>Điểm trú ẩn</small><strong>Trong khu vực đã chọn</strong></span>
          <b>{communeShelters.length}</b>
        </div>
        {communeShelters[0] && (
          <button className="nearest-shelter" onClick={() => onSelectShelter(communeShelters[0].id)}>
            <Building2 size={20} />
            <span><small>Điểm trú ẩn đề xuất</small><strong>{communeShelters[0].name}</strong><em>{communeShelters[0].capacity ? `Sức chứa ${communeShelters[0].capacity} người` : "Sức chứa chưa có dữ liệu xác minh"}</em></span>
            <ArrowRight size={18} />
          </button>
        )}
        <button className="primary-action"><Navigation size={18} /> Xem hướng dẫn sơ tán</button>
      </div>
    </aside>
  );
}
