import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ serviceId: string }> }
) {
  try {
    const { serviceId } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/services/${serviceId}/disconnect`,
      { method: 'POST' }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error disconnecting service session:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
