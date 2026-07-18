import { type NextRequest, NextResponse } from "next/server";
import { getCommuneOverview } from "@/server/dataGateway";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ code: string }> },
) {
  try {
    const { code } = await context.params;
    const riskLevelValue = Number(request.nextUrl.searchParams.get("riskLevel"));
    const riskLevel = Number.isFinite(riskLevelValue) && riskLevelValue > 0 ? riskLevelValue : undefined;
    const data = await getCommuneOverview(
      code,
      request.nextUrl.searchParams.get("hazard") ?? undefined,
      riskLevel,
    );
    return NextResponse.json({ data }, { headers: { "Cache-Control": "private, max-age=300" } });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Không thể tải dự báo." },
      { status: 503 },
    );
  }
}
