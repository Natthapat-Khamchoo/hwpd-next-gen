import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'hwpd-next-gen-jwt-secret-key-2026';

export async function GET(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('token')?.value;

    if (!token) {
      return NextResponse.json({ status: 'error', message: 'Unauthorized' }, { status: 401 });
    }

    const decoded = jwt.verify(token, JWT_SECRET) as any;
    const userStation = decoded.station; 
    
    const allowedRoles = ['Division_Admin', 'Division_Commander', 'HQ_Admin', 'Super_Commander'];
    if (!allowedRoles.includes(decoded.role)) {
      return NextResponse.json({ status: 'error', message: 'Permission Denied' }, { status: 403 });
    }

    const { searchParams } = new URL(request.url);
    const queryDivision = searchParams.get('division'); // e.g. "5", "all"

    // Determine the division scope
    let divisionPrefix = '';
    if (userStation !== '00' && userStation !== 'HQ') {
      divisionPrefix = userStation[0];
    } else if (queryDivision && queryDivision !== 'all') {
      divisionPrefix = queryDivision;
    }

    const stationFilter = divisionPrefix === '' ? {} : { stationId: { startsWith: divisionPrefix } };

    const divDaily = await prisma.dailyResult.findMany({
      where: {
        isActive: true,
        status: 'Approved',
        ...stationFilter
      }
    });
    
    const divArrests = await prisma.arrest.findMany({
      where: {
        isActive: true,
        status: 'Approved',
        ...stationFilter
      }
    });

    const divAccidents = await prisma.accident.findMany({
      where: {
        isActive: true,
        status: 'Approved',
        ...stationFilter
      }
    });

    const totalV43 = divDaily.reduce((acc, cur) => acc + cur.v43, 0);
    const totalService = divDaily.reduce((acc, cur) => acc + cur.service, 0);
    const totalV42 = divDaily.reduce((acc, cur) => acc + cur.v42, 0);
    const totalV20 = divDaily.reduce((acc, cur) => acc + cur.v20, 0);
    const totalArrests = divArrests.reduce((acc, cur) => acc + cur.suspectCount, 0);
    const totalAccidents = divAccidents.length;
    const totalDeaths = divAccidents.reduce((acc, cur) => acc + cur.deadCount, 0);
    const totalInjured = divAccidents.reduce((acc, cur) => acc + cur.injuredCount, 0);

    let stationStatsList: any[] = [];

    if (divisionPrefix === '') {
      // Aggregate by Division (กก.1 - กก.8)
      const divisionsList = ['1', '2', '3', '4', '5', '6', '7', '8'];
      const divisionStatsMap: Record<string, any> = {};
      divisionsList.forEach(div => {
        divisionStatsMap[div] = { v43: 0, service: 0, v42: 0, v20: 0, arrests: 0, accidents: 0, dead: 0, injured: 0 };
      });

      divDaily.forEach(row => {
        const div = row.stationId[0];
        if (divisionStatsMap[div]) {
          divisionStatsMap[div].v43 += row.v43;
          divisionStatsMap[div].service += row.service;
          divisionStatsMap[div].v42 += row.v42;
          divisionStatsMap[div].v20 += row.v20;
        }
      });

      divArrests.forEach(row => {
        const div = row.stationId[0];
        if (divisionStatsMap[div]) {
          divisionStatsMap[div].arrests += row.suspectCount;
        }
      });

      divAccidents.forEach(row => {
        const div = row.stationId[0];
        if (divisionStatsMap[div]) {
          divisionStatsMap[div].accidents += 1;
          divisionStatsMap[div].dead += row.deadCount;
          divisionStatsMap[div].injured += row.injuredCount;
        }
      });

      stationStatsList = Object.entries(divisionStatsMap).map(([id, stats]) => ({
        stationId: `กก.${id}`,
        ...stats
      }));
    } else {
      // Aggregate by Station (ส.ทล.1 - ส.ทล.6) inside the division
      const stList = ['1', '2', '3', '4', '5', '6'].map(x => `${divisionPrefix}${x}`);
      const stationStatsMap: Record<string, any> = {};
      stList.forEach(st => {
        stationStatsMap[st] = { v43: 0, service: 0, v42: 0, v20: 0, arrests: 0, accidents: 0, dead: 0, injured: 0 };
      });

      divDaily.forEach(row => {
        if (stationStatsMap[row.stationId]) {
          stationStatsMap[row.stationId].v43 += row.v43;
          stationStatsMap[row.stationId].service += row.service;
          stationStatsMap[row.stationId].v42 += row.v42;
          stationStatsMap[row.stationId].v20 += row.v20;
        }
      });

      divArrests.forEach(row => {
        if (stationStatsMap[row.stationId]) {
          stationStatsMap[row.stationId].arrests += row.suspectCount;
        }
      });

      divAccidents.forEach(row => {
        if (stationStatsMap[row.stationId]) {
          stationStatsMap[row.stationId].accidents += 1;
          stationStatsMap[row.stationId].dead += row.deadCount;
          stationStatsMap[row.stationId].injured += row.injuredCount;
        }
      });

      stationStatsList = Object.entries(stationStatsMap).map(([id, stats]) => ({
        stationId: `ส.ทล.${id[1]} กก.${id[0]}`,
        ...stats
      }));
    }

    return NextResponse.json({
      status: 'success',
      data: {
        totals: {
          v43: totalV43,
          service: totalService,
          v42: totalV42,
          v20: totalV20,
          arrests: totalArrests,
          accidents: totalAccidents,
          deaths: totalDeaths,
          injured: totalInjured
        },
        stations: stationStatsList
      }
    });

  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.toString() }, { status: 500 });
  }
}
