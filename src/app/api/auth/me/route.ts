import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

export async function GET() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('token')?.value;

    if (!token) {
      return NextResponse.json({ status: 'fail', message: 'Not logged in' }, { status: 401 });
    }

    const decoded = jwt.verify(token, JWT_SECRET) as any;
    return NextResponse.json({ status: 'success', user: decoded });
  } catch (error: any) {
    return NextResponse.json({ status: 'fail', message: 'Session expired' }, { status: 401 });
  }
}
