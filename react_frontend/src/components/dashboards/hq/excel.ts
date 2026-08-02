/**
 * ส่งออกตารางเป็นไฟล์ Excel ฝั่งเบราว์เซอร์
 *
 * ต้นฉบับมีปุ่ม export 7 จุดในหน้า ฝอ. และทุกจุดสร้างไฟล์จากข้อมูลที่โหลดมาแสดง
 * อยู่แล้ว ไม่ได้ยิงกลับไปที่ server ที่นี่ทำแบบเดียวกัน — ไม่กินโควตาอ่านของ Google
 * เพิ่ม ไม่ต้องรอ Render ตื่นจาก sleep และไม่ต้องเพิ่ม endpoint ต่อหนึ่งปุ่ม
 *
 * เขียนเป็น SpreadsheetML 2003 (XML ล้วน) แทน .xlsx จริงซึ่งเป็น zip — จะได้ไม่ต้อง
 * ลงไลบรารีเพิ่ม Excel กับ LibreOffice เปิดได้ทั้งคู่ และรองรับภาษาไทยเมื่อประกาศ
 * encoding เป็น UTF-8
 */

export type Cell = string | number | null | undefined;

const escapeXml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');

const cellXml = (value: Cell): string => {
  if (value === null || value === undefined || value === '') return '<Cell/>';
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `<Cell><Data ss:Type="Number">${value}</Data></Cell>`;
  }
  // ข้อความล้วนเสมอ ไม่ปล่อยให้ Excel เดาชนิดเอง ไม่งั้นเลขคดีหรือรหัสสถานีที่ขึ้นต้น
  // ด้วยศูนย์จะโดนตัดศูนย์หน้าทิ้ง
  return `<Cell><Data ss:Type="String">${escapeXml(String(value))}</Data></Cell>`;
};

const sheetXml = (name: string, rows: Cell[][]): string => {
  const body = rows
    .map((row) => `<Row>${row.map(cellXml).join('')}</Row>`)
    .join('');
  // ชื่อชีตห้ามมี : \ / ? * [ ] และยาวเกิน 31 ตัว Excel จะปฏิเสธทั้งไฟล์
  const safe = escapeXml(name.replace(/[:\\/?*[\]]/g, '-').slice(0, 31));
  return `<Worksheet ss:Name="${safe}"><Table>${body}</Table></Worksheet>`;
};

const workbookXml = (sheets: { name: string; rows: Cell[][] }[]): string =>
  `<?xml version="1.0" encoding="UTF-8"?>` +
  `<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ` +
  `xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">` +
  sheets.map((s) => sheetXml(s.name, s.rows)).join('') +
  `</Workbook>`;

const save = (filename: string, xml: string): void => {
  // BOM ไว้ข้างหน้า ไม่งั้น Excel บน Windows เปิดแล้วภาษาไทยเป็นสี่เหลี่ยม
  const blob = new Blob(['﻿', xml], { type: 'application/vnd.ms-excel;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.xls`;
  link.click();
  URL.revokeObjectURL(url);
};

/** ส่งออกตารางเดียว */
export const downloadSheet = (filename: string, rows: Cell[][], sheetName = 'ข้อมูล'): void =>
  save(filename, workbookXml([{ name: sheetName, rows }]));

/** ส่งออกหลายตารางในไฟล์เดียว แยกเป็นชีตละหมวด */
export const downloadWorkbook = (filename: string, sheets: { name: string; rows: Cell[][] }[]): void =>
  save(filename, workbookXml(sheets.filter((s) => s.rows.length)));
