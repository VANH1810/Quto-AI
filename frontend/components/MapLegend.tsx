import { Building2, CircleDot, MapPin } from "lucide-react";
import { RISK_META } from "@/utils/risk";
import type { RiskLevel } from "@/types";

export function MapLegend() {
  return (
    <div className="map-legend">
      <strong>Mức cảnh báo</strong>
      <div className="legend-scale">
        {(Object.keys(RISK_META) as unknown as RiskLevel[]).map((level) => (
          <span key={level}><i style={{ background: RISK_META[level].color }} />Cấp {level}</span>
        ))}
      </div>
      <div className="marker-key">
        <span><CircleDot size={15} /> Trung tâm xã</span>
        <span><Building2 size={15} /> Điểm trú ẩn</span>
        <span><MapPin size={15} /> Vị trí của bạn</span>
      </div>
      <small>Dữ liệu ranh giới và cảnh báo đang dùng cho mục đích minh họa.</small>
    </div>
  );
}
