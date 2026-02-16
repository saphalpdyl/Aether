import { NextResponse } from "next/server";

import { BACKEND_URL } from "@/config/backend";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const range = searchParams.get("range") || "1h";
    const bucketSeconds = searchParams.get("bucket_seconds") || "10";

    const res = await fetch(
      `${BACKEND_URL}/api/stats/traffic-series?range=${encodeURIComponent(range)}&bucket_seconds=${encodeURIComponent(bucketSeconds)}`,
      {
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    if (!res.ok) {
      return NextResponse.json({ error: "Backend request failed", status: res.status }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching traffic series:", error);
    return NextResponse.json({ error: "Failed to fetch traffic series", message: String(error) }, { status: 500 });
  }
}
