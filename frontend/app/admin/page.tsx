import type { Metadata } from "next";
import { AdminConsole } from "@/components/admin/AdminConsole";

export const metadata: Metadata = { title: "Điều hành PCTT · Điện Biên", description: "Bảng điều hành cảnh báo sớm thiên tai Điện Biên" };

export default function AdminPage() { return <AdminConsole page="overview" />; }
