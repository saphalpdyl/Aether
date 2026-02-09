import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/bngs`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch BNGs' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching BNGs:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
