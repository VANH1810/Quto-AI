import { AdminConsole } from "@/components/admin/AdminConsole";

export default async function SosDetail({ params }: { params: Promise<{ sosId: string }> }) { const { sosId } = await params; return <AdminConsole page="sos" sosId={sosId} />; }
