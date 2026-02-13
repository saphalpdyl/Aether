import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ customerId: string }> }
) {
  try {
    const { customerId } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/customers/${encodeURIComponent(customerId)}/sessions`,
      { cache: 'no-store' }
    );
    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error fetching customer sessions:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
