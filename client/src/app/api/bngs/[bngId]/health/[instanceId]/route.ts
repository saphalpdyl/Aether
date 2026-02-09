import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ bngId: string; instanceId: string }> }
) {
  try {

    const resolvedParams = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/bngs/${resolvedParams.bngId}/health/${resolvedParams.instanceId}`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch BNG health' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching BNG health:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
