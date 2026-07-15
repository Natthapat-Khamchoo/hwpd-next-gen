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

    const decoded = jwt.verify(token, JWT_SECRET) as any;
    const currentUser = decoded.username;
    
    const { recordId, sheetName } = await request.json();

    if (!recordId || !sheetName) {
      return NextResponse.json({ status: 'error', message: 'ข้อมูลไม่ครบถ้วน' }, { status: 400 });
    }

    let result = null;
    const baseQuery = { recordId, actionBy: currentUser, status: 'Pending' };

    switch (sheetName) {
      case 'tb_DailyResult':
        result = await prisma.dailyResult.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_Arrests':
        result = await prisma.arrest.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_Accidents':
        result = await prisma.accident.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_OtherDuties':
        result = await prisma.otherDuty.updateMany({
          where: { recordId, actionBy: currentUser },
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_RoyalGuard':
        result = await prisma.royalGuard.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_FuelOil':
        result = await prisma.fuelOil.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_Mission':
        result = await prisma.mission.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_Inventory':
        result = await prisma.inventory.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      case 'tb_Repairs':
        result = await prisma.repair.updateMany({
          where: baseQuery,
          data: { status: 'Canceled', isActive: false }
        });
        break;
      default:
        return NextResponse.json({ status: 'error', message: 'ไม่พบประเภทรายงานนี้' }, { status: 400 });
    }

    if (result && result.count === 0) {
      return NextResponse.json({ status: 'error', message: 'ไม่พบเอกสาร หรือเอกสารได้รับการอนุมัติไปแล้ว ไม่สามารถยกเลิกได้' }, { status: 400 });
    }

    return NextResponse.json({
      status: 'success',
      message: 'ยกเลิกรายการส่งเอกสารเรียบร้อยแล้ว'
    });

  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.toString() }, { status: 500 });
  }
}
