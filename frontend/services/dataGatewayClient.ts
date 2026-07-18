export class DataGatewayError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "DataGatewayError";
  }
}

export async function dataGatewayRequest<T>(
  path: string,
  token?: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/data${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json().catch(() => null) as
    | { data?: T; error?: string }
    | null;
  if (!response.ok) {
    const retryAfter = Number.parseInt(response.headers.get("retry-after") ?? "", 10);
    throw new DataGatewayError(
      payload?.error ?? `Yêu cầu thất bại (${response.status})`,
      response.status,
      Number.isFinite(retryAfter) ? retryAfter : undefined,
    );
  }
  return payload?.data as T;
}
