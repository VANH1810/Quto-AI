import { type NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function backendBaseUrl() {
  const value = (process.env.APP_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL)?.trim();
  if (!value) throw new Error("API cứu hộ/UBND chưa được cấu hình.");
  return value.replace(/\/$/, "");
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    if (!body || body.length > 10_000) {
      return NextResponse.json({ error: "Nội dung SOS không hợp lệ." }, { status: 400 });
    }

    const deviceId = request.headers.get("x-device-id")?.trim();
    const forwardedFor = request.headers.get("x-forwarded-for")?.trim();
    const realIp = request.headers.get("x-real-ip")?.trim();
    const response = await fetch(`${backendBaseUrl()}/api/v1/rescue/sos`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(deviceId ? { "X-Device-ID": deviceId } : {}),
        ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : realIp ? { "X-Real-IP": realIp } : {}),
      },
      body,
    });
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    const retryAfter = response.headers.get("retry-after");

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail ?? `API cứu hộ trả về lỗi ${response.status}. Tín hiệu chưa được xác nhận.` },
        {
          status: response.status,
          headers: retryAfter ? { "Retry-After": retryAfter } : undefined,
        },
      );
    }

    return NextResponse.json(
      { data: payload },
      { status: 201, headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Không thể kết nối API cứu hộ/UBND." },
      { status: 503 },
    );
  }
}
