import { type NextRequest, NextResponse } from "next/server";
import { adminData } from "@/server/dataGateway";

export const dynamic = "force-dynamic";

async function handle(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  try {
    const { segments } = await context.params;
    const [resource, id] = segments;
    const body = request.method === "GET" ? undefined : await request.text();
    const data = await adminData(resource, {
      id,
      method: request.method,
      body: body || undefined,
      authorization: request.headers.get("authorization") ?? undefined,
    });
    return NextResponse.json({ data });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Không thể tải dữ liệu quản trị." },
      { status: 503 },
    );
  }
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
