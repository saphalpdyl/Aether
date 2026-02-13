import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ routerName: string }> }
) {
  try {
    const { routerName } = await params;
    const body = await request.json();
    const response = await fetch(
      `${BACKEND_URL}/api/routers/${encodeURIComponent(routerName)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error updating router:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ routerName: string }> }
) {
  try {
    const { routerName } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/routers/${encodeURIComponent(routerName)}`,
      { method: 'DELETE' }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error deleting router:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
