import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    // Validate request body
    if (!body.service_id || !body.name || !body.command) {
      return NextResponse.json(
        { error: 'Missing required fields: service_id, name and command' },
        { status: 400 }
      );
    }

    const response = await fetch(`${BACKEND_URL}/api/simulation/cmd`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        service_id: body.service_id,
        name: body.name,
        command: body.command,
      }),
    });
    
    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error executing simulation command:', error);
    return NextResponse.json(
      { error: 'Failed to execute simulation command' },
      { status: 500 }
    );
  }
}
