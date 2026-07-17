export type AlertStatus = "detected" | "pending_approval" | "approved" | "dispatching" | "sent" | "partial_failed" | "rejected";

export interface RiskSummary { code: string; name: string; risk_level: number; risk_color: string; risk_label: string; top_hazard: string | null; top_hazard_label: string | null; }
export interface DispatchRecord { channel: string; target: string; recipients: number; delivered: number; status: "ok" | "failed" | "retrying"; detail: string; }
export interface AlertRecord { id: string; status: AlertStatus; event: { hazard: string; commune_code: string; commune_name: string; risk_level: number; risk_color: string; risk_label: string; provenance: { source: string; rule: string; observed_at: string }; recommended_actions: string[] }; bulletins: Array<{ lang: string; title: string; body: string }>; dispatches: DispatchRecord[]; created_at: string; }
export interface RecipientRecord { id: string; full_name: string; address: string; channel: string; status: "sent" | "failed" | "home_visit"; detail: string; }
export interface Health { status: "ok"; version: string; weather_provider: string; db_backend: string; llm_provider: string; }
export interface DashboardSnapshot { health: Health; risks: RiskSummary[]; alerts: AlertRecord[]; recipients: RecipientRecord[]; authenticated: boolean; }
