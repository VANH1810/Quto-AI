import "./admin.css";
import { AdminSessionProvider } from "@/components/admin/AdminSessionProvider";

export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AdminSessionProvider>{children}</AdminSessionProvider>;
}
