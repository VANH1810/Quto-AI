import { Check, ExternalLink, MapPin, RotateCw, Send } from "lucide-react";
import type { RecipientRecord } from "@/types/admin";

interface RecipientPanelProps { recipients: RecipientRecord[]; isBusy: boolean; onContact: (id: string) => void; onRetryAll: () => void; }

export function RecipientPanel({ recipients, isBusy, onContact, onRetryAll }: RecipientPanelProps) {
  return <section className="recipient-panel" aria-labelledby="recipient-title">
    <header className="panel-heading"><div><div className="heading-line"><h2 id="recipient-title">Chưa nhận được cảnh báo - Mường Pồn, cấp 3</h2><span>{recipients.length} người</span></div><p>Đã thử Zalo + SMS. Không có biên nhận sau 10 phút, cần liên hệ trực tiếp.</p></div></header>
    {recipients.length === 0 ? <div className="recipient-empty"><Check size={20} /> Không còn người chờ liên hệ trực tiếp.</div> : <ul className="recipient-list">{recipients.map((recipient) => <li key={recipient.id}><div className="recipient-copy"><strong>{recipient.full_name}</strong><small><MapPin size={13} /> {recipient.address}</small></div><span className="recipient-reason">{recipient.detail || `${recipient.channel} chưa có biên nhận`}</span><button type="button" onClick={() => onContact(recipient.id)} disabled={isBusy}><Check size={15} /> Đã liên hệ</button></li>)}</ul>}
    <footer className="recipient-actions"><button type="button" className="button button--quiet" onClick={() => window.open("/", "_blank", "noopener,noreferrer")}><ExternalLink size={16} /> Mở bản đồ cảnh báo</button><button type="button" className="button button--quiet" onClick={onRetryAll} disabled={isBusy || recipients.length === 0}><RotateCw size={16} /> Gửi lại tất cả</button><button type="button" className="button button--accent" onClick={onRetryAll} disabled={isBusy || recipients.length === 0}><Send size={16} /> Gửi danh sách trưởng bản</button></footer>
  </section>;
}
