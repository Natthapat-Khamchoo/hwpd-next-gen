import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

export async function POST(request: Request) {
  try {
    const { username, password } = await request.json();

    if (!username || !password) {
      return NextResponse.json(
        { status: 'fail', message: 'กรุณากรอกชื่อผู้ใช้และรหัสผ่าน' },
        { status: 400 }
      );
    }

    const user = await prisma.user.findUnique({
      where: { username: String(username).trim() },
    });

    if (!user) {
      return NextResponse.json(
        { status: 'fail', message: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง' },
        { status: 401 }
      );
    }

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return NextResponse.json(
        { status: 'fail', message: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง' },
        { status: 401 }
      );
    }

    // Resolve help assignment
    let effectiveStation = user.station;
    if (user.role === 'Unit_Staff' || user.role === 'Station_Admin') {
      if (user.helpGoTo) {
        effectiveStation = user.helpGoTo;
      }
    }

    const payload = {
      username: user.username,
      fullName: user.fullName,
      station: effectiveStation,
      homeStation: user.station,
      unit: user.unit,
      role: user.role,
    };

    const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '1d' });

    const response = NextResponse.json({
      status: 'success',
      user: payload,
    });

    response.cookies.set('token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 86400, // 1 day
      path: '/',
    });

    return response;
  } catch (error: any) {
    return NextResponse.json(
      { status: 'fail', message: 'เกิดข้อผิดพลาด: ' + error.toString() },
      { status: 500 }
    );
  }
}
