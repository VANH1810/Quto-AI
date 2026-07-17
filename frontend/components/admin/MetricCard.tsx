import type { LucideIcon } from "lucide-react";

interface MetricCardProps { label: string; value: string; suffix?: string; tone?: "default" | "critical" | "warning"; icon: LucideIcon; }

export function MetricCard({ label, value, suffix, tone = "default", icon: Icon }: MetricCardProps) {
  return <article className={`metric-card metric-card--${tone}`}><span className="metric-icon" aria-hidden="true"><Icon size={18} /></span><p>{label}</p><strong>{value}{suffix && <small>{suffix}</small>}</strong></article>;
}
