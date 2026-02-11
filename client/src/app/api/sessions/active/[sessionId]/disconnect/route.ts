import { NextResponse } from 'next/server';
import { BACKEND_URL } from '@/config/backend';

export async function POST(
  request: Request,
  context: { params: Promise<{ sessionId: string }> }
) {
  try {
    const params = await context.params;
    
    console.log('Sending disconnect for session:', params.sessionId);
    
    const url = `${BACKEND_URL}/api/sessions/active/${params.sessionId}/disconnect`;
    console.log('Backend URL:', url);
    
    const response = await fetch(url, {
      method: 'POST',
      cache: 'no-store',
    });

    console.log('Backend response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend error:', errorText);
      return NextResponse.json(
        { error: 'Failed to disconnect session', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log('Backend response data:', data);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error disconnecting session:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    );
  }
}
