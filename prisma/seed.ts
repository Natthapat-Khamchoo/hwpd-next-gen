import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcryptjs';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database with dynamic stations from CSV...');

  // 1. Clear existing database
  await prisma.user.deleteMany();
  await prisma.charge.deleteMany();
  await prisma.dailyResult.deleteMany();
  await prisma.arrest.deleteMany();
  await prisma.accident.deleteMany();

  const passwordHash = await bcrypt.hash('password123', 10);

  // 2. Read and parse stations_config.csv (trying multiple fallback paths)
  const pathsToTry = [
    path.join(process.cwd(), 'stations_config.csv'),
    path.join(process.cwd(), 'hwpd-next-gen', 'stations_config.csv'),
    path.join(process.cwd(), 'my-appsscript-project', 'hwpd-next-gen', 'stations_config.csv'),
    path.join(__dirname, '../stations_config.csv'),
    path.join(__dirname, '../../stations_config.csv')
  ];

  let csvPath = '';
  for (const p of pathsToTry) {
    if (fs.existsSync(p)) {
      csvPath = p;
      break;
    }
  }

  if (!csvPath) {
    throw new Error('stations_config.csv not found! Please place it in the project root directory.');
  }

  const csvContent = fs.readFileSync(csvPath, 'utf-8');
  const lines = csvContent.split('\n');
  
  interface StationConfigRow {
    division: string;
    stationId: string;
    stationName: string;
    units: string[];
  }

  const configStations: StationConfigRow[] = [];
  const uniqueDivisions = new Set<string>();

  // Skip header
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const parts = line.split(',');
    if (parts.length >= 4) {
      const division = parts[0].trim();
      const stationId = parts[1].trim();
      const stationName = parts[2].trim();
      const unitsString = parts[3].trim();
      const units = unitsString.split(/[;,]/).map(u => u.trim()).filter(Boolean);

      configStations.push({
        division,
        stationId,
        stationName,
        units
      });
      uniqueDivisions.add(division);
    }
  }

  console.log(`Parsed ${configStations.length} stations and ${uniqueDivisions.size} divisions from CSV.`);

  // 3. Create central users
  const users = [
    {
      username: 'super_commander',
      password: passwordHash,
      fullName: 'พล.ต.ต. คงกฤช เลิศศิริปัญญา (ผบก.ทล.)',
      station: '00',
      unit: 'ผบก.ทล.',
      role: 'Super_Commander',
      phone: '0819999999',
      code: 'NAT-CMD-01',
      note: 'ผู้บัญชาการระดับประเทศ ดูแดชบอร์ดสรุปสถิติทั่วประเทศ'
    },
    {
      username: 'hq_admin',
      password: passwordHash,
      fullName: 'พ.ต.อ. แอดมิน บก.ทล. (HQ Admin)',
      station: '00',
      unit: 'ฝอ.บก.ทล.',
      role: 'HQ_Admin',
      phone: '0812345678',
      code: 'HQ-ADM-01',
      note: 'ส่วนกลาง ดูแลระบบจัดการผู้ใช้งานทั้งประเทศ'
    }
  ];

  // 4. Create division users dynamically
  uniqueDivisions.forEach(div => {
    // Division Commander
    users.push({
      username: `commander${div}`,
      password: passwordHash,
      fullName: `พ.ต.อ. ผู้กำกับการ กองกำกับการ ${div} (ผกก.${div})`,
      station: `${div}0`,
      unit: `ฝอ.กก.${div}`,
      role: 'Division_Commander',
      phone: `081000000${div}`,
      code: `DIV${div}-CMD-01`,
      note: `ผู้บังคับบัญชา กองกำกับการ ${div}`
    });

    // Division Admin
    users.push({
      username: `admin${div}`,
      password: passwordHash,
      fullName: `พ.ต.ท. แอดมิน กองกำกับการ ${div} (ฝอ.กก.${div})`,
      station: `${div}0`,
      unit: `ฝอ.กก.${div}`,
      role: 'Division_Admin',
      phone: `082000000${div}`,
      code: `DIV${div}-ADM-01`,
      note: `ผู้ดูแลคิวงานรอตรวจสอบของ กก.${div}`
    });
  });

  // 5. Create station users dynamically
  configStations.forEach(st => {
    // Station Admin (สว.ส.ทล.x)
    users.push({
      username: `station${st.stationId}`,
      password: passwordHash,
      fullName: `พ.ต.ต. สว.${st.stationName}`,
      station: st.stationId,
      unit: st.units[0] || 'สายตรวจประจำสถานี',
      role: 'Station_Admin',
      phone: `083${st.stationId}000`,
      code: `ST${st.stationId}-ADM-01`,
      note: `สารวัตรสถานี ${st.stationName}`
    });

    // Unit Staff (สายตรวจ ส.ทล.x)
    users.push({
      username: `staff${st.stationId}`,
      password: passwordHash,
      fullName: `ด.ต. สายตรวจประจำ ${st.stationName}`,
      station: st.stationId,
      unit: st.units[0] || 'สายตรวจประจำสถานี',
      role: 'Unit_Staff',
      phone: `084${st.stationId}000`,
      code: `ST${st.stationId}-STF-01`,
      note: `สายตรวจปฏิบัติการสถานี ${st.stationName}`
    });
  });

  console.log(`Writing ${users.length} users to DB...`);
  for (const user of users) {
    await prisma.user.create({
      data: user
    });
  }

  // 6. Create standard charges
  const charges = [
    'ขับรถเร็วเกินกว่าอัตราที่กฎหมายกำหนด',
    'ไม่สวมหมวกนิรภัยขณะขับขี่รถจักรยานยนต์',
    'ขับรถในขณะมึนเมาสุรา',
    'ไม่มีใบอนุญาตขับขี่',
    'ไม่คาดเข็มขัดนิรภัยขณะขับขี่',
    'ใช้อุปกรณ์สื่อสารขณะขับรถ',
    'ขับรถย้อนศร',
    'ฝ่าฝืนสัญญาณไฟจราจร'
  ];

  for (const charge of charges) {
    await prisma.charge.create({
      data: { name: charge }
    });
  }

  // 7. Generate mock reports dynamically for the last 30 days
  const officers = ['ด.ต. อนันต์ ทองใบ', 'ด.ต. ชูเกียรติ ยอดดี', 'จ.ส.ต. ปฏิพล ชัยชนะ', 'ส.ต.อ. ศักดา แสงคำ'];
  const today = new Date();

  console.log('Generating historical mock records nationwide...');

  for (let i = 1; i <= 30; i++) {
    const reportDate = new Date();
    reportDate.setDate(today.getDate() - i);
    const dateStr = reportDate.toISOString().split('T')[0];

    // For each station, generate reports
    for (const st of configStations) {
      const stationId = st.stationId;
      const unitId = st.units[Math.floor(Math.random() * st.units.length)] || 'สายตรวจหลัก';
      const actionBy = officers[Math.floor(Math.random() * officers.length)];

      const v43 = Math.floor(Math.random() * 12) + 3;
      const service = Math.floor(Math.random() * 6) + 1;
      const v42 = Math.floor(Math.random() * 8) + 1;
      const v20 = Math.floor(Math.random() * 4) + 1;

      // DailyResults
      await prisma.dailyResult.create({
        data: {
          recordId: `STD-${stationId}-${dateStr.replace(/-/g, '')}-${i}`,
          actionBy,
          status: 'Approved',
          isActive: true,
          actualDate: dateStr,
          stationId,
          unitId,
          reportDateTime: `${dateStr}T08:00:00`,
          v43,
          service,
          v42,
          v20,
          chargesText: 'ตรวจกวดขันวินัยจราจรและจับกุมผู้ฝ่าฝืนกฎหมาย',
          notes: 'ตรวจเส้นทางสายหลักในพื้นที่รับผิดชอบเหตุการณ์ทั่วไปปกติ',
        }
      });

      // Arrests (35% chance)
      if (Math.random() > 0.65) {
        const suspectCount = Math.floor(Math.random() * 2) + 1;
        await prisma.arrest.create({
          data: {
            recordId: `ARR-${stationId}-${dateStr.replace(/-/g, '')}-${i}`,
            actionBy,
            status: 'Approved',
            isActive: true,
            actualDate: dateStr,
            stationId,
            unitId,
            reportDateTime: `${dateStr}T14:20:00`,
            suspectCount,
            suspectsText: suspectCount === 1 ? 'นายสมชาย ดีงาม' : 'นายสมชาย ดีงาม, นายประกรณ์ ชัยชนะ',
            offense: 'ขับรถเร็วเกินกว่าอัตราที่กฎหมายกำหนด',
            circumstances: 'ตรวจจับด้วยกล้องตรวจจับความเร็วแบบพกพาเกินกำหนด 120 กม./ชม.',
          }
        });
      }

      // Accidents (15% chance)
      if (Math.random() > 0.85) {
        const deadCount = Math.random() > 0.95 ? 1 : 0;
        const injuredCount = Math.floor(Math.random() * 2);
        await prisma.accident.create({
          data: {
            recordId: `ACC-${stationId}-${dateStr.replace(/-/g, '')}-${i}`,
            actionBy,
            status: 'Approved',
            isActive: true,
            actualDate: dateStr,
            stationId,
            unitId,
            reportDateTime: `${dateStr}T21:00:00`,
            route: 'ทล.หลัก',
            km: `${Math.floor(Math.random() * 200) + 10}+100`,
            direction: 'ขาเข้ากรุงเทพ',
            locDetails: 'เกิดอุบัติเหตุบริเวณจุดกลับรถ',
            deadCount,
            injuredCount,
            hospital: 'โรงพยาบาลศูนย์ประจำจังหวัด',
            mainVehicle: 'รถยนต์กระบะ',
            oppVehicle: 'รถยนต์นั่งส่วนบุคคล',
            cHuman: 90.0,
            cVehicle: 10.0,
            cRoad: 0.0,
            cEnv: 0.0
          }
        });
      }
    }
  }

  console.log('Seeding completed successfully using stations_config.csv!');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
