import { ArrowRight, Building2, CheckCircle2, Clock3, MapPinned, Navigation, PhoneCall, ShieldAlert, Users } from "lucide-react";
import type { CommuneAlert, CommuneCenter, Coordinates, SelectedPlace, Shelter, UserPosition } from "@/types";
import { googleMapsDirectionsUrl } from "@/utils/directions";
import { haversineKm } from "@/utils/geo";
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
}

export function DetailPanel({ selection, alerts, communes, shelters, userPosition, routeOrigin, onSelectShelter }: DetailPanelProps) {
  const selectedAlert = selection?.type === "commune" ? alerts.find((alert) => alert.communeCode === selection.id) : undefined;
  const selectedCommune = selectedAlert ? communes.find((item) => item.code === selectedAlert.communeCode) : undefined;
  const selectedShelter = selection?.type === "shelter" ? shelters.find((item) => item.id === selection.id) : undefined;

  if (selection?.type === "user" && userPosition) {
    const nearest = [...shelters].sort((a, b) => haversineKm(userPosition, a) - haversineKm(userPosition, b))[0];
    return (
      <aside className="detail-panel">
        <div className="detail-top safe"><span className="detail-icon"><Navigation size={22} /></span><div><small>Vị trí hiện tại</small><h2>Đã xác định vị trí của bạn</h2></div></div>
        <div className="detail-body">
          <p className="detail-description">Độ chính xác khoảng {Math.round(userPosition.accuracy)} m. Chỉ sử dụng vị trí để hiển thị trên thiết bị này.</p>
          {nearest && <button className="nearest-shelter" onClick={() => onSelectShelter(nearest.id)}><Building2 size={20} /><span><small>Điểm trú ẩn gần nhất</small><strong>{nearest.name}</strong><em>{haversineKm(userPosition, nearest).toFixed(1)} km đường chim bay</em></span><ArrowRight size={18} /></button>}
        </div>
      </aside>
    );
  }

  if (selectedShelter) {
    const alert = alerts.find((item) => item.communeCode === selectedShelter.communeCode);
    const risk = alert ? RISK_META[alert.riskLevel] : RISK_META[1];
    return (
      <aside className="detail-panel">
        <div className="detail-top shelter"><span className="detail-icon"><Building2 size={22} /></span><div><small>Điểm trú ẩn</small><h2>{selectedShelter.name}</h2></div></div>
        <div className="detail-body">
          <div className="shelter-facts">
            <span><MapPinned size={18} /><b>Địa chỉ</b><small>{selectedShelter.address}</small></span>
            <span><Building2 size={18} /><b>Loại địa điểm</b><small>{SHELTER_KIND_LABELS[selectedShelter.kind]}</small></span>
            <span><Users size={18} /><b>Sức chứa dự kiến</b><small>{selectedShelter.capacity ? `${selectedShelter.capacity} người` : "Chưa có dữ liệu xác minh"}</small></span>
            <span><Navigation size={18} /><b>Tọa độ đích</b><small>{selectedShelter.lat}, {selectedShelter.lon}</small></span>
          </div>
          <div className="current-risk"><span>Nguy cơ tại khu vực</span><strong style={{ color: risk.color }}>Cấp {alert?.riskLevel ?? 1} · {alert?.hazardLabel ?? "Đang theo dõi"}</strong></div>
          <a className="primary-action" href={googleMapsDirectionsUrl(selectedShelter, routeOrigin)} target="_blank" rel="noopener noreferrer"><Navigation size={18} /> Xem đường đi đến điểm trú ẩn</a>
          <button className="secondary-action"><PhoneCall size={17} /> Gọi ban chỉ huy xã</button>
        </div>
      </aside>
    );
  }

  if (!selectedAlert || !selectedCommune) {
    return (
      <aside className="detail-panel empty-detail"><ShieldAlert size={32} /><h2>Chọn một khu vực</h2><p>Chạm vào một xã trên bản đồ để xem cảnh báo và hướng dẫn an toàn.</p></aside>
    );
  }

  const risk = RISK_META[selectedAlert.riskLevel];
  const communeShelters = shelters.filter((item) => item.communeCode === selectedAlert.communeCode);
  return (
    <aside className="detail-panel">
      <div className="detail-top" style={{ background: `linear-gradient(135deg, ${risk.color}, ${risk.color}d8)` }}>
        <span className="detail-icon"><ShieldAlert size={23} /></span>
        <div><small>{userPosition ? risk.label : "Vị trí gần đúng"}</small><h2>{selectedCommune.name}</h2><p>{selectedCommune.district}</p></div>
      </div>
      <div className="detail-body">
        <div className="alert-meta"><span className="hazard-badge">{selectedAlert.hazardLabel}</span><span><Clock3 size={14} /> {selectedAlert.updatedAt}</span></div>
        <h3>{selectedAlert.headline}</h3>
        <p className="detail-description">{selectedAlert.detail}</p>
        <div className="action-card">
          <strong>Việc cần làm ngay</strong>
          {selectedAlert.recommendedActions.map((action) => <p key={action}><CheckCircle2 size={17} />{action}</p>)}
        </div>
        <div className="stat-row"><span><small>Dân số tham khảo</small><strong>{selectedCommune.population.toLocaleString("vi-VN")}</strong></span><span><small>Điểm trú ẩn</small><strong>{communeShelters.length}</strong></span></div>
        {communeShelters[0] && <button className="nearest-shelter" onClick={() => onSelectShelter(communeShelters[0].id)}><Building2 size={20} /><span><small>Điểm trú ẩn đề xuất</small><strong>{communeShelters[0].name}</strong><em>{communeShelters[0].capacity ? `Sức chứa ${communeShelters[0].capacity} người` : "Sức chứa chưa có dữ liệu xác minh"}</em></span><ArrowRight size={18} /></button>}
        <button className="primary-action"><Navigation size={18} /> Xem hướng dẫn sơ tán</button>
      </div>
    </aside>
  );
}
