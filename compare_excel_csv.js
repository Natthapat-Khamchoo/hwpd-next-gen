const XLSX = require('xlsx');
const path = require('path');
const fs = require('fs');

const excelPath = path.join(__dirname, 'ข้อมูลหน่วยบริการ ตร.ทล. ปี 68.xlsx');
const csvPath = path.join(__dirname, 'stations_config.csv');

try {
  const workbook = XLSX.readFile(excelPath);
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  const excelData = XLSX.utils.sheet_to_json(sheet);

  // Group Excel units by station
  const excelStations = {};
  let currentStationId = null;

  for (let i = 0; i < excelData.length; i++) {
    const row = excelData[i];
    const text = (row["__EMPTY"] || "").trim();

    const match = text.match(/^ส\.ทล\.(\d+)\s*กก\.(\d+)/);
    if (match) {
      currentStationId = match[2] + match[1];
      excelStations[currentStationId] = [];
      continue;
    }

    const unitNo = row["สำรวจหน่วยบริการ ปี 2568"];
    if (unitNo && currentStationId) {
      const unitName = (row["__EMPTY"] || "").trim();
      if (unitName) {
        excelStations[currentStationId].push({
          no: unitNo,
          name: unitName,
          desc: (row["__EMPTY_1"] || "").trim()
        });
      }
    }
  }

  // Read CSV
  const csvContent = fs.readFileSync(csvPath, 'utf-8');
  const csvLines = csvContent.split('\n');
  const csvStations = {};
  for (let i = 1; i < csvLines.length; i++) {
    const line = csvLines[i].trim();
    if (!line) continue;
    const parts = line.split(',');
    if (parts.length >= 4) {
      const id = parts[1].trim();
      const units = parts[3].trim().split(';').map(u => u.trim());
      csvStations[id] = units;
    }
  }

  console.log("=== COMPARE STATIONS ===");
  Object.keys(excelStations).sort().forEach(id => {
    const excelUnits = excelStations[id];
    const csvUnits = csvStations[id] || [];
    
    console.log(`\nStation ${id}:`);
    console.log(`Excel count: ${excelUnits.length} | CSV count: ${csvUnits.length}`);
    console.log(`Excel list:`, excelUnits.map(u => `${u.no}: ${u.name} (${u.desc})`));
    console.log(`CSV list:`, csvUnits);
  });

} catch (err) {
  console.error(err);
}
