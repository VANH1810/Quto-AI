import { NextResponse } from "next/server";
import { getStoredSnapshot } from "@/server/dataGateway";

export const dynamic = "force-dynamic";

export async function GET() {
  if (process.env.NODE_ENV === "production" || process.env.ALLOW_MOCK_SNAPSHOT_EXPORT !== "true") {
    return new NextResponse(null, { status: 404 });
  }
  return NextResponse.json(await getStoredSnapshot(), {
    headers: { "Content-Disposition": 'attachment; filename="quto-data.snapshot.json"' },
  });
}
