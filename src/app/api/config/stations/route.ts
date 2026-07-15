import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

// Default configuration map if CSV doesn't exist yet
const DEFAULT_CONFIG: Record<string, { name: string; units: string[] }> = {
  '11': { name: 'ส.ทล.1 กก.1 (อยุธยา)', units: ['อยุธยา', 'วังน้อย', 'บางปะอิน', 'ฝอ.กก.1'] },
  '12': { name: 'ส.ทล.2 กก.1 (สระบุรี)', units: ['สระบุรี', 'แก่งคอย', 'มวกเหล็ก'] },
  '21': { name: 'ส.ทล.1 กก.2 (สุพรรณบุรี)', units: ['สุพรรณบุรี', 'ศรีประจันต์', 'อู่ทอง'] },
  '31': { name: 'ส.ทล.1 กก.3 (ชลบุรี)', units: ['ชลบุรี', 'บางแสน', 'ศรีราชา'] },
  '41': { name: 'ส.ทล.1 กก.4 (ขอนแก่น)', units: ['ขอนแก่น', 'ชุมแพ', 'บ้านไผ่'] },
  '51': { name: 'ส.ทล.1 กก.5 (ตาก)', units: ['แม่สอด', 'สามเงา', 'เมืองตาก', 'พรานกระต่าย', 'ฝอ.กก.5'] },
  '52': { name: 'ส.ทล.2 กก.5 (ลำปาง)', units: ['ลำปาง', 'เถิน', 'ห้างฉัตร'] },
  '61': { name: 'ส.ทล.1 กก.6 (อุบลราชธานี)', units: ['อุบลราชธานี', 'วารินชำราบ', 'พิบูลมังสาหาร'] },
  '71': { name: 'ส.ทล.1 กก.7 (สงขลา)', units: ['สงขลา', 'หาดใหญ่', 'จะนะ'] },
  '81': { name: 'ส.ทล.1 กก.8 (ทางหลวงพิเศษ)', units: ['ลาดกระบัง', 'ธัญบุรี', 'ทับช้าง'] }
};

let cachedConfig: Record<string, { name: string; units: string[] }> | null = null;

export async function GET() {
  try {
    if (cachedConfig) {
      return NextResponse.json({ status: 'success', data: cachedConfig });
    }

    // Try multiple possible paths for stations_config.csv
    const pathsToTry = [
      path.join(process.cwd(), 'stations_config.csv'),
      path.join(process.cwd(), 'hwpd-next-gen', 'stations_config.csv'),
      path.join(process.cwd(), 'my-appsscript-project', 'hwpd-next-gen', 'stations_config.csv')
    ];

    let csvPath = '';
    for (const p of pathsToTry) {
      if (fs.existsSync(p)) {
        csvPath = p;
        break;
      }
    }
    
    if (csvPath) {
      console.log(`[API Config] Reading stations configuration from: ${csvPath}`);
      const fileContent = await fs.promises.readFile(csvPath, 'utf-8');
      const lines = fileContent.split('\n');
      const config: Record<string, { name: string; units: string[] }> = {};
      
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const parts = line.split(',');
        if (parts.length >= 4) {
          const stationId = parts[1].trim();
          const stationName = parts[2].trim();
          const unitsString = parts[3].trim();
          const units = unitsString.split(/[;,]/).map(u => u.trim()).filter(Boolean);
          
          config[stationId] = {
            name: stationName,
            units: units
          };
        }
      }
      
      cachedConfig = config;
      return NextResponse.json({ status: 'success', data: config });
    }
    
    console.warn(`[API Config] stations_config.csv not found in searched paths. Falling back to default config.`);
    cachedConfig = DEFAULT_CONFIG;
    return NextResponse.json({ status: 'success', data: DEFAULT_CONFIG });
    
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.toString() }, { status: 500 });
  }
}
