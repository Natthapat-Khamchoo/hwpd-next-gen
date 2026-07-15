import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('token')?.value;
    if (!token) {
      return NextResponse.json({ status: 'error', message: 'Unauthorized' }, { status: 401 });
    }

    let decoded;
    try {
      decoded = jwt.verify(token, JWT_SECRET) as any;
    } catch (err) {
      return NextResponse.json({ status: 'error', message: 'Session Expired or Invalid Token' }, { status: 401 });
    }

    // Role-Based Access Control
    const allowedRoles = ['Super_Commander', 'HQ_Admin', 'Division_Commander', 'Division_Admin', 'Station_Admin'];
    if (!allowedRoles.includes(decoded.role)) {
      return NextResponse.json({ status: 'error', message: 'Permission Denied: Unauthorized role' }, { status: 403 });
    }

    const { recordId, sheetName, action } = await request.json(); 
    if (!recordId || !sheetName || !action) {
      return NextResponse.json({ status: 'error', message: 'ข้อมูลไม่ครบถ้วน' }, { status: 400 });
    }

    const newStatus = action === 'approve' ? 'Approved' : 'Canceled';
    const isActive = action === 'approve'; 

    let result = null;

    switch (sheetName) {
      case 'tb_DailyResult':
        result = await prisma.dailyResult.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_Arrests':
        result = await prisma.arrest.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_Accidents':
        result = await prisma.accident.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_RoyalGuard':
        result = await prisma.royalGuard.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_OtherDuties':
        result = await prisma.otherDuty.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_Inventory':
        result = await prisma.inventory.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_Repairs':
        result = await prisma.repair.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      case 'tb_FuelOil':
        result = await prisma.fuelOil.update({
          where: { recordId },
          data: { status: newStatus, isActive }
        });
        break;
      default:
        return NextResponse.json({ status: 'error', message: 'ไม่รองรับประเภทข้อมูลนี้' }, { status: 400 });
    }

    return NextResponse.json({
      status: 'success',
      message: action === 'approve' ? 'อนุมัติรายการเรียบร้อย' : 'ยกเลิกรายการเรียบร้อยแล้ว',
      data: result
    });

  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: 'Internal Server Error' }, { status: 500 });
  }
}
