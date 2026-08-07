/**
 * กติกาว่าฟอร์มจับกุม "ครบ" เมื่อไหร่ ใช้ร่วมกันระหว่างปุ่มส่งรายงานกับปุ่มออกเอกสาร
 *
 * แยกออกมาจาก ArrestForm เพราะสองปุ่มเคยตรวจคนละชุด ปุ่มออกเอกสารเช็คแค่ชื่อผู้ต้องหา
 * จึงออกบันทึกจับกุมจากข้อมูลที่ยังยื่นรายงานไม่ได้ กลายเป็นเอกสารราชการที่ไม่มีรายงาน
 * ในระบบรองรับ เก็บกติกาไว้ที่เดียวแล้วเรียกจากทั้งสองปุ่ม ความต่างแบบนั้นจึงเกิดซ้ำไม่ได้
 */

export interface ArrestSuspect {
  name: string;
  idCard: string;
  nat: string;
  age: string;
  address: string;
}

export interface ArrestChargeRow {
  value: string;
  other: string;
}

export interface ArrestFormState {
  team: string[];
  chargeRows: ArrestChargeRow[];
  suspects: ArrestSuspect[];
  f: Record<string, string>;
}

/** ข้อหาที่กรอกจริง แปลงแถว "อื่นๆ (พิมพ์ข้อหาเอง)" เป็นข้อความที่พิมพ์ไว้ */
export const chargeList = (rows: ArrestChargeRow[]): string[] =>
  rows.map((c) => (c.value === '__OTHER__' ? c.other.trim() : c.value)).filter(Boolean);

export const isWarrantArrest = (f: Record<string, string>): boolean =>
  ['จับตามหมาย', 'จับหมาย Bigdata', 'จับหมาย Bodyworn'].includes(f.arrestType) ||
  f.warrantType !== 'ไม่ใช่หมายจับ';

/**
 * คืน **รายชื่อช่องที่ยังขาด** ไม่ใช่แค่ true/false เพราะข้อความ "ข้อมูลไม่ครบ" เฉย ๆ
 * ทำให้ผู้ใช้ต้องไล่หาเองทั้งฟอร์มว่าตกช่องไหน ฟอร์มนี้ยาวที่สุดในระบบ
 */
export const missingArrestFields = ({ team, chargeRows, suspects, f }: ArrestFormState): string[] => {
  const missing: string[] = [];

  if (team.filter(Boolean).length === 0) missing.push('ชุดจับกุม (อย่างน้อย 1 นาย)');
  if (chargeList(chargeRows).length === 0) missing.push('ข้อหา (อย่างน้อย 1 ข้อหา)');

  suspects.forEach((s, i) => {
    const gaps = [
      !s.name && 'ชื่อ-สกุล',
      !s.idCard && 'เลขบัตร ปชช./พาสปอร์ต',
      !s.nat && 'สัญชาติ',
      !s.age && 'อายุ',
      !s.address && 'ที่อยู่',
    ].filter(Boolean);
    if (gaps.length) missing.push(`ผู้ต้องหาคนที่ ${i + 1} — ${gaps.join(', ')}`);
  });

  if (!f.category) missing.push('หัวข้อการจับกุม');
  if (!f.location) missing.push('สถานที่จับกุม/เกิดเหตุ');
  if (!f.lat || !f.lng) missing.push('พิกัด ละติจูด/ลองจิจูด (กดปุ่ม "ปักหมุด" หรือ "ระบุพิกัด")');
  if (!f.items) missing.push('ของกลาง (ข้อความ)');
  if (!f.circumstances) missing.push('พฤติการณ์');
  if (!f.forwarding) missing.push('การดำเนินการส่งต่อ');

  if (isWarrantArrest(f) && (!f.warrantScope || f.warrantScope === 'ไม่ใช่หมายจับ'))
    missing.push('ขอบเขตหมาย — หมายใน (บช.ก.) หรือ หมายนอก');

  return missing;
};
