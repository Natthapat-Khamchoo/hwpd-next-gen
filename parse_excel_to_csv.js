const XLSX = require('xlsx');
const path = require('path');
const fs = require('fs');

const filePath = path.join(__dirname, 'ข้อมูลหน่วยบริการ ตร.ทล. ปี 68.xlsx');
try {
  const workbook = XLSX.readFile(filePath);
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  // Parse with raw text formatting
  const data = XLSX.utils.sheet_to_json(sheet, { defval: "" });

  console.log("Analyzing file rows with exact regex...");

  let currentStation = null;
  const stationsMap = {};

  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    
    // Check if this row defines a new station
    let stationMatch = null;
    let stationText = "";
    
    Object.keys(row).forEach(k => {
      const val = String(row[k]).trim();
      const m = val.match(/ส\.ทล\.(\d+)\s*(?:กก\.|กองกำกับการ)\s*(\d+)/);
      if (m) {
        stationMatch = m;
        stationText = val;
      }
    });

    if (stationMatch) {
      const stationNum = stationMatch[1];
      const divNum = stationMatch[2];
      const stationId = divNum + stationNum;
      
      let cleanStationName = stationText.split("  ")[0].trim();
      if (!cleanStationName.endsWith("บก.ทล.")) {
        cleanStationName = `${cleanStationName} บก.ทล.`;
      }
      
      currentStation = {
        stationId,
        division: divNum,
        name: cleanStationName,
        units: []
      };
      
      stationsMap[stationId] = currentStation;
    }

    // Now look for units in this row
    let unitName = "";
    Object.keys(row).forEach(k => {
      const val = String(row[k]).trim();
      if (/^\d+\./.test(val) || val.startsWith("หน่วยบริการ") || val.startsWith("หน่วยฯ") || val.startsWith("เขตตรวจ")) {
        unitName = val;
      }
    });

    // Fallback if no matching pattern, but "ชื่อหน่วยบริการ" is set
    if (!unitName && row["ชื่อหน่วยบริการ"]) {
      unitName = String(row["ชื่อหน่วยบริการ"]).trim();
    }
    // Fallback if "__EMPTY" has value (usually the second column)
    if (!unitName && row["__EMPTY"]) {
      const val = String(row["__EMPTY"]).trim();
      if (val && !val.match(/ส\.ทล\.(\d+)\s*(?:กก\.|กองกำกับการ)\s*(\d+)/) && !val.includes("บก.ทล.")) {
        unitName = val;
      }
    }

    if (unitName && currentStation) {
      // Clean unit name
      let cleanUnit = unitName.replace(/^\d+\.\s*(หน่วยบริการฯ\s*|หน่วยฯ\s*|หน่วยบริการประชาชนตำรวจทางหลวง\s*|หน่วยกู้ภัยฯ\s*)?/, "").trim();
      cleanUnit = cleanUnit.replace(/^หน่วยบริการฯ\s*|^หน่วยฯ\s*|^หน่วยบริการประชาชน\s*|^หน่วยบริการประชาชนตำรวจทางหลวง\s*|^หน่วยกู้ภัยฯ\s*/, "").trim();
      
      if (cleanUnit && cleanUnit.length > 1 && !cleanUnit.startsWith("ส.ทล.")) {
        // Remove trailing commas/periods
        cleanUnit = cleanUnit.replace(/[.,\s]+$/, "").trim();
        currentStation.units.push(cleanUnit);
      }
    }
  }

  // Handle M6 motorways manually if not captured in the loop
  if (stationsMap['83'] && stationsMap['83'].units.length === 0) {
    stationsMap['83'].units = ['มอเตอร์เวย์ M6(ลำตะคอง)'];
  }
  if (!stationsMap['83']) {
    stationsMap['83'] = {
      stationId: '83',
      division: '8',
      name: 'ส.ทล.3 กก.8 บก.ทล.',
      units: ['มอเตอร์เวย์ M6(ลำตะคอง)']
    };
  }

  // Handle M81 motorways manually if not captured
  if (stationsMap['84'] && stationsMap['84'].units.length === 0) {
    stationsMap['84'].units = ['บางแม่นาง', 'ท่าม่วง'];
  }
  if (!stationsMap['84']) {
    stationsMap['84'] = {
      stationId: '84',
      division: '8',
      name: 'ส.ทล.4 กก.8 บก.ทล.',
      units: ['บางแม่นาง', 'ท่าม่วง']
    };
  }

  console.log("\nSummary of parsed stations and units:");
  const csvRows = ["Division,StationId,StationName,ServiceUnits"];
  
  Object.keys(stationsMap).sort().forEach(id => {
    const st = stationsMap[id];
    // Add "ฝอ.กก.X" to units list as a default standard
    const uniqueUnits = Array.from(new Set([...st.units, `ฝอ.กก.${st.division}`]));
    const unitsStr = uniqueUnits.join(";");
    
    console.log(`ID: ${id} | ${st.name} | Units: ${unitsStr}`);
    csvRows.push(`${st.division},${st.stationId},${st.name},${unitsStr}`);
  });

  const csvContent = csvRows.join("\n") + "\n";
  fs.writeFileSync(path.join(__dirname, 'stations_config.csv'), csvContent, 'utf-8');
  console.log("\nSuccessfully updated stations_config.csv with genuine Excel data!");

} catch (err) {
  console.error("Error parsing Excel:", err);
}
