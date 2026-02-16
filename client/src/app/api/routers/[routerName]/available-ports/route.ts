import { NextResponse } from "next/server";

import { BACKEND_URL } from "@/config/backend";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ routerName: string }> }
) {
  try {
    const { routerName } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/routers/${encodeURIComponent(routerName)}/available-ports`,
      { cache: "no-store" }
    );

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Error fetching available router ports:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
