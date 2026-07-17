import { BellRing, Radio, ShieldCheck } from "lucide-react";

export function AppHeader() {
  return (
    <header className="app-header">
      <div className="brand-mark" aria-hidden="true"><ShieldCheck size={25} strokeWidth={2.2} /></div>
      <div className="brand-copy">
        <span>Bản tin an toàn</span>
        <strong>Cảnh báo thiên tai Điện Biên</strong>
      </div>
      <div className="header-status">
        <span className="live-status"><i /><Radio size={15} /> Đang cập nhật trực tiếp</span>
        <span className="last-update">Cập nhật 06:15 · 17/07/2026</span>
      </div>
      <button className="icon-button header-alert" aria-label="Thông báo mới">
        <BellRing size={20} /><span>3</span>
      </button>
    </header>
  );
}
