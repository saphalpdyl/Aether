import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/simulation/get_simulate_options`, {
      cache: 'no-store',
    });
    
    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`);
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error fetching simulation options:', error);
    return NextResponse.json(
      { error: 'Failed to fetch simulation options' },
      { status: 500 }
    );
  }
}
