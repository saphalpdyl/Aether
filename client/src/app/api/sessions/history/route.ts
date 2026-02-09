import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/config/backend";

export async function GET() {
  try {
    console.log(BACKEND_URL)
    const res = await fetch(`${BACKEND_URL}/api/sessions/history`, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "Backend request failed", status: res.status },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching session history:", error);
    return NextResponse.json(
      { error: "Failed to fetch session history", message: String(error) },
      { status: 500 }
    );
  }
}
