import { describe, expect, it } from 'vitest';
import { buildV20CopyText, formatPreviewDate, getFrontendStationData } from './formHelpers';

/**
 * ข้อความที่เจ้าหน้าที่คัดลอกไปวางในกลุ่ม LINE
 *
 * ข้อความพวกนี้เป็นสิ่งที่ผู้บังคับบัญชาอ่านจริง การพิมพ์ตัวเลขผิดช่องหรือแปลงวันที่
 * ผิดปีจะไม่มีอะไรฟ้อง เพราะมันเป็นแค่สตริง เทสจึงต้องล็อกรูปแบบไว้
 */

describe('buildV20CopyText', () => {
  const base = {
    stationName: 'ส.ทล.1 กก.5 บก.ทล.',
    dateText: '4 ส.ค. 69',
    warrant: 4,
    flagrante: 6,
    v20: 10,
  };

  it('มีครบทุกบรรทัดตามรูปแบบที่หน่วยกำหนด', () => {
    const text = buildV20CopyText(base);
    expect(text).toContain('📢 รายงานผลการปฏิบัติ ว.20');
    expect(text).toContain('🗓️ วันที่: 4 ส.ค. 69 | หน่วย: ส.ทล.1 กก.5 บก.ทล.');
    expect(text).toContain('⚖️ จับกุมตามหมายจับ: 4 ราย');
    expect(text).toContain('🚨 จับกุมซึ่งหน้า: 6 ราย');
    expect(text).toContain('📊 ยอด ว.20 รวม: 10 ราย');
  });

  it('ไม่มีบรรทัดพิกัด เพราะสรุปนี้ไม่ได้ผูกกับจุดใดจุดหนึ่ง', () => {
    // การใส่พิกัดปลอมหรือเว้นวงเล็บว่างไว้จะทำให้คนอ่านเข้าใจผิดว่าเป็นพิกัดจริง
    expect(buildV20CopyText(base)).not.toContain('📍');
  });

  it('ต่อท้ายรายการข้อหาเมื่อมีข้อมูล', () => {
    const text = buildV20CopyText({ ...base, chargesText: 'ขับเร็วเกินกำหนด (7)' });
    expect(text).toContain('📋 แบ่งตามข้อหา');
    expect(text).toContain('ขับเร็วเกินกำหนด (7)');
  });

  it('ไม่มีหัวข้อข้อหาโผล่มาลอย ๆ เมื่อไม่มีข้อมูล', () => {
    for (const chargesText of [undefined, '', '   ']) {
      expect(buildV20CopyText({ ...base, chargesText })).not.toContain('📋');
    }
  });

  it('ยอดศูนย์ยังต้องแสดง ไม่ใช่ซ่อน', () => {
    // "0 ราย" กับ "ไม่มีบรรทัดนั้น" คนอ่านตีความต่างกัน — อย่างหลังอ่านว่ายังไม่ได้รายงาน
    const text = buildV20CopyText({ ...base, warrant: 0, flagrante: 0, v20: 0 });
    expect(text).toContain('⚖️ จับกุมตามหมายจับ: 0 ราย');
    expect(text).toContain('🚨 จับกุมซึ่งหน้า: 0 ราย');
  });
});

describe('formatPreviewDate', () => {
  it('แปลง ค.ศ. เป็น พ.ศ. และใช้ชื่อเดือนไทย', () => {
    expect(formatPreviewDate('2026-08-04')).toBe('4 ส.ค. 69');
  });

  it('รวมเวลาเมื่อค่าที่ส่งมามีเวลาด้วย', () => {
    expect(formatPreviewDate('2026-08-04T09:30')).toBe('4 ส.ค. 69 เวลา 09.30 น.');
  });

  it('ค่าที่ว่างหรือผิดรูปแบบไม่ทำให้พัง', () => {
    expect(formatPreviewDate('')).toBe('-');
    expect(formatPreviewDate(undefined)).toBe('-');
  });
});

describe('getFrontendStationData', () => {
  it('รหัสสถานีที่ลงท้ายด้วย 0 คือฝ่ายอำนวยการของ กก. นั้น', () => {
    expect(getFrontendStationData('50').f).toBe('ฝอ.กก.5 บก.ทล.');
  });

  it('รหัสสถานีอื่นแปลงเป็นชื่อ ส.ทล.', () => {
    expect(getFrontendStationData('51').f).toBe('ส.ทล.1 กก.5 บก.ทล.');
  });
});
