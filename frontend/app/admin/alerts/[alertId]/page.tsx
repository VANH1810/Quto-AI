import { AdminConsole } from "@/components/admin/AdminConsole";
export default async function AlertDetailPage({ params }: { params: Promise<{ alertId: string }> }) { const { alertId } = await params; return <AdminConsole page="alerts" alertId={alertId} />; }
