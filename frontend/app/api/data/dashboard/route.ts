import { NextResponse } from "next/server";
import { getDashboardData } from "@/server/dataGateway";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json({ data: await getDashboardData() }, {
      headers: { "Cache-Control": "private, max-age=60" },
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Không thể tải dữ liệu." },
      { status: 503 },
    );
  }
}
