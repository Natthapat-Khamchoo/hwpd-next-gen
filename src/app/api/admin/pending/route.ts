import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';
import * as jwt from 'jsonwebtoken';
import { getStationFilter } from '@/app/api/reports/route';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

export async function GET(request: Request) {
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

    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type') || 'general'; 
    const reqStationId = decoded.station;
    const isStaff = decoded.role === 'Unit_Staff';

    // Only allow users with legitimate roles
    const allowedRoles = ['Super_Commander', 'HQ_Admin', 'Division_Commander', 'Division_Admin', 'Station_Admin', 'Unit_Staff'];
    if (!allowedRoles.includes(decoded.role)) {
      return NextResponse.json({ status: 'error', message: 'Permission Denied' }, { status: 403 });
    }

    const users = await prisma.user.findMany({ select: { username: true, fullName: true } });
    const userMap = new Map(users.map(u => [u.username, u.fullName]));

    let pendingList: any[] = [];

    // Construct common where clause
    const stationFilter = getStationFilter(reqStationId);
    const userFilter = isStaff ? { actionBy: decoded.username } : {};
    
    const getQueryCondition = () => {
      return {
        status: 'Pending',
        isActive: true,
        ...stationFilter,
        ...userFilter
      };
    };

    if (type === 'general') {
      const daily = await prisma.dailyResult.findMany({ where: getQueryCondition() });
      const arrests = await prisma.arrest.findMany({ where: getQueryCondition() });
      const accidents = await prisma.accident.findMany({ where: getQueryCondition() });
      const guards = await prisma.royalGuard.findMany({ where: getQueryCondition() });
      const others = await prisma.otherDuty.findMany({ where: getQueryCondition() });

      daily.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'ผลการปฏิบัติ/ว.20',
          sheetName: 'tb_DailyResult',
          icon: 'fa-chart-pie'
        });
      });

      arrests.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'รายงานจับกุม',
          sheetName: 'tb_Arrests',
          icon: 'fa-handcuffs'
        });
      });

      accidents.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'รายงานอุบัติเหตุ',
          sheetName: 'tb_Accidents',
          icon: 'fa-car-burst'
        });
      });

      guards.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'รายงานรับเสด็จ',
          sheetName: 'tb_RoyalGuard',
          icon: 'fa-shield-halved'
        });
      });

      others.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'ว.4 จิตอาสา/ช่วยเหลือ',
          sheetName: 'tb_OtherDuties',
          icon: 'fa-hands-holding-child'
        });
      });
    } else if (type === 'inventory') {
      const inventory = await prisma.inventory.findMany({ where: getQueryCondition() });
      const repairs = await prisma.repair.findMany({ where: getQueryCondition() });

      inventory.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'รับ/คืน พัสดุ',
          sheetName: 'tb_Inventory',
          icon: 'fa-boxes-stacked'
        });
      });

      repairs.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'แจ้งซ่อม/ชำรุด',
          sheetName: 'tb_Repairs',
          icon: 'fa-wrench'
        });
      });
    } else if (type === 'fuel') {
      const fuel = await prisma.fuelOil.findMany({ where: getQueryCondition() });

      fuel.forEach(row => {
        pendingList.push({
          recordId: row.recordId,
          timestamp: row.createdAt.toISOString(),
          rawTime: row.createdAt.getTime(),
          actionBy: userMap.get(row.actionBy) || row.actionBy,
          unitId: row.unitId,
          formType: 'น้ำมันรถยนต์',
          sheetName: 'tb_FuelOil',
          icon: 'fa-gas-pump'
        });
      });
    }

    pendingList.sort((a, b) => a.rawTime - b.rawTime);
    return NextResponse.json({ status: 'success', data: pendingList });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: 'Internal Server Error' }, { status: 500 });
  }
}
