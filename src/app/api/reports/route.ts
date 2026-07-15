import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

function generateRecordId(prefix: string, stationId: string): string {
  const timestamp = new Date();
  const yyMMddHHmm = timestamp.toISOString().slice(2, 10).replace(/-/g, '') + '-' + timestamp.toTimeString().slice(0, 5).replace(/:/g, '');
  const rand = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
  return `${prefix}-${stationId}-${yyMMddHHmm}-${rand}`;
}

function checkStationMatch(reqStationId: string, rowStationId: string): boolean {
  if (reqStationId === rowStationId) return true;
  if (reqStationId === '00' || reqStationId === '0' || reqStationId.toUpperCase() === 'HQ') return true;
  if (reqStationId.endsWith('0') && reqStationId.length === 2) {
    return reqStationId[0] === rowStationId[0];
  }
  return false;
}

export function getStationFilter(reqStationId: string): any {
  if (reqStationId === '00' || reqStationId === '0' || reqStationId.toUpperCase() === 'HQ') {
    return {};
  }
  if (reqStationId.endsWith('0') && reqStationId.length === 2) {
    return { stationId: { startsWith: reqStationId[0] } };
  }
  return { stationId: reqStationId };
}

// 🟢 GET: Fetch reports with visibility permissions based on user role and station
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
    const type = searchParams.get('type') || 'daily'; // daily, arrest, accident, checkpoint, royal-guard
    const status = searchParams.get('status') || 'all'; // Approved, Pending, all
    
    const userStation = decoded.station;
    let results: any[] = [];

    // Query filters
    const baseFilter: any = { isActive: true, ...getStationFilter(userStation) };
    if (status !== 'all') {
      baseFilter.status = status;
    }

    switch (type) {
      case 'daily':
        results = await prisma.dailyResult.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'arrest':
        results = await prisma.arrest.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'accident':
        results = await prisma.accident.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'checkpoint':
        results = await prisma.otherDuty.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'royal-guard':
        results = await prisma.royalGuard.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'fuel':
        results = await prisma.fuelOil.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'mission':
        results = await prisma.mission.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'inventory':
        results = await prisma.inventory.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'repair':
        results = await prisma.repair.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      case 'document':
        results = await prisma.onlineDocument.findMany({ where: baseFilter, orderBy: { createdAt: 'desc' } });
        break;
      default:
        return NextResponse.json({ status: 'error', message: 'Invalid report type' }, { status: 400 });
    }

    return NextResponse.json({
      status: 'success',
      data: results
    });

  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: 'Internal Server Error' }, { status: 500 });
  }
}

// 🟢 POST: Submit reports
export async function POST(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('token')?.value;

    if (!token) {
      return NextResponse.json({ status: 'error', message: 'กรุณาเข้าสู่ระบบก่อนทำรายการ' }, { status: 401 });
    }

    let decoded;
    try {
      decoded = jwt.verify(token, JWT_SECRET) as any;
    } catch (err) {
      return NextResponse.json({ status: 'error', message: 'กรุณาเข้าสู่ระบบใหม่ (Session Expired หรือไม่ถูกต้อง)' }, { status: 401 });
    }

    const { type, data } = await request.json();

    if (!type || !data) {
      return NextResponse.json({ status: 'error', message: 'ข้อมูลไม่ครบถ้วน' }, { status: 400 });
    }

    const timestamp = new Date();
    const actualDate = data.reportDateTime ? data.reportDateTime.split('T')[0] : timestamp.toISOString().split('T')[0];
    const stationId = decoded.station;
    const actionBy = decoded.username;
    
    let recordId = '';
    let result = null;

    switch (type) {
      case 'daily':
        recordId = generateRecordId('STD', stationId);
        result = await prisma.dailyResult.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            v43: parseInt(data.v43) || 0,
            service: parseInt(data.service) || 0,
            v42: parseInt(data.v42) || 0,
            v20: parseInt(data.v20) || 0,
            chargesText: data.chargesText || '-',
            mapLink: data.mapLink || '',
            signatureUrl: data.signatureUrl || '',
            notes: data.notes || '',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'arrest':
        recordId = generateRecordId('ARR', stationId);
        result = await prisma.arrest.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            suspectCount: parseInt(data.suspectCount) || 0,
            suspectsText: data.suspectsText || '',
            offense: data.offense || '',
            circumstances: data.circumstances || '',
            mapLink: data.mapLink || '',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'accident':
        recordId = generateRecordId('ACC', stationId);
        result = await prisma.accident.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            route: data.route || '',
            km: data.km || '',
            direction: data.direction || '',
            locDetails: data.locDetails || '',
            deadCount: parseInt(data.deadCount) || 0,
            injuredCount: parseInt(data.injuredCount) || 0,
            hospital: data.hospital || '',
            mainVehicle: data.mainVehicle || '',
            oppVehicle: data.oppVehicle || '',
            cHuman: parseFloat(data.cHuman) || 0,
            cVehicle: parseFloat(data.cVehicle) || 0,
            cRoad: parseFloat(data.cRoad) || 0,
            cEnv: parseFloat(data.cEnv) || 0,
            solutions: data.solutions || '',
            govDamage: data.govDamage || '',
            carNumber: data.carNumber || '',
            jointUnits: data.jointUnits || '',
            description: data.description || '',
            lat: data.lat || '',
            lng: data.lng || '',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'checkpoint':
        recordId = generateRecordId('CHK', stationId);
        result = await prisma.otherDuty.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            dutyType: 'ตั้งจุดตรวจ',
            details: `รถวิทยุตรวจเขต: ${data.carNumber || ''}, สถานที่ตั้ง: ${data.location || ''}`,
            location: data.location || '',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'mission':
        recordId = generateRecordId('MIS', stationId);
        result = await prisma.mission.create({
          data: {
            recordId,
            actionBy,
            status: 'Active',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            startTime: data.startTime || '',
            endTime: data.endTime || '',
            targetUnits: data.targetUnits || '',
            missionDetails: data.missionDetails || '',
            location: data.location || '',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'inventory':
        recordId = generateRecordId('INV', stationId);
        result = await prisma.inventory.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            actionDateTime: data.actionDateTime || timestamp.toISOString(),
            transactionType: data.transactionType || '',
            category: data.category || '',
            itemName: data.itemName || '',
            qty: parseFloat(data.qty) || 0,
            unitMeasure: data.unitMeasure || '',
            receiverName: data.receiverName || '',
            signatureUrl: data.signatureUrl || '',
            notes: data.notes || ''
          }
        });
        break;

      case 'repair':
        recordId = generateRecordId('REP', stationId);
        result = await prisma.repair.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            brokenItem: data.brokenItem || '',
            issueDetail: data.issueDetail || '',
            reporterName: data.reporterName || '',
            repairStatus: 'รอดำเนินการ',
            folderUrl: data.folderUrl || ''
          }
        });
        break;

      case 'royal-guard':
        recordId = generateRecordId('RG', stationId);
        result = await prisma.royalGuard.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            reportType: data.reportType || 'prep',
            reportDateTime: data.reportDateTime || timestamp.toISOString(),
            commanders: data.commanders || '',
            missionName: data.missionName || '',
            carNumbers: data.carNumbers || '',
            details: data.details || '',
            folderUrl: data.folderUrl || '',
            targetCount: parseInt(data.targetCount) || 1
          }
        });
        break;

      case 'fuel':
        recordId = generateRecordId('FUEL', stationId);
        result = await prisma.fuelOil.create({
          data: {
            recordId,
            actionBy,
            status: 'Pending',
            actualDate,
            stationId,
            unitId: data.unitId || decoded.unit,
            recordType: data.recordType || 'เติมน้ำมัน',
            actionDateTime: data.actionDateTime || timestamp.toISOString(),
            actionPerson: data.actionPerson || '',
            plateNumber: data.plateNumber || '',
            currentMileage: parseFloat(data.currentMileage) || 0,
            liters: parseFloat(data.liters) || 0,
            fuelType: data.fuelType || '',
            price: parseFloat(data.price) || 0,
            receiptNumber: data.receiptNumber || '',
            prevMileage: parseFloat(data.prevMileage) || 0,
            distanceUsed: parseFloat(data.distanceUsed) || 0
          }
        });
        break;

      default:
        return NextResponse.json({ status: 'error', message: 'ไม่รองรับประเภทรายงานนี้' }, { status: 400 });
    }

    return NextResponse.json({
      status: 'success',
      message: 'บันทึกรายงานเรียบร้อยแล้ว',
      data: result
    });

  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: 'เกิดข้อผิดพลาด: ' + error.toString() }, { status: 500 });
  }
}
