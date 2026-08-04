import { describe, expect, it } from 'vitest';
import { MIN_SHORT_EDGE, checkDimensions } from './mediaQc';

/**
 * เกณฑ์คุณภาพสื่อ 1080p (requirement ข้อ 13 — BR-01)
 *
 * ค่าเดียวกันนี้ถูกตรวจซ้ำฝั่ง backend (`pr_service.check_dimensions`) ถ้าสองฝั่ง
 * ตีความต่างกัน ผู้ใช้จะเห็นว่าไฟล์ผ่านแล้วส่งไป แต่ระบบจัดเข้าคิวรอพิจารณา
 * เทสชุดนี้จึงเขียนคู่กับชุดฝั่ง Python ที่มีเคสเหมือนกัน
 */
describe('checkDimensions', () => {
  it('ภาพแนวนอน Full HD ผ่านเกณฑ์', () => {
    expect(checkDimensions(1920, 1080).passed).toBe(true);
  });

  it('ภาพแนวตั้งจากมือถือก็ผ่านเกณฑ์', () => {
    // วัดด้านสั้น ไม่ใช่ความสูง — เช็คแค่ความสูงจะตกภาพแนวนอนที่ถูกต้อง
    expect(checkDimensions(1080, 1920).passed).toBe(true);
  });

  it('พอดีเกณฑ์ถือว่าผ่าน', () => {
    expect(checkDimensions(MIN_SHORT_EDGE, MIN_SHORT_EDGE).passed).toBe(true);
  });

  it('ต่ำกว่าเกณฑ์ไม่ผ่าน และบอกเหตุผลที่อ่านรู้เรื่อง', () => {
    const result = checkDimensions(1280, 720);
    expect(result.passed).toBe(false);
    expect(result.reason).toContain('1280x720');
    expect(result.reason).toContain(`${MIN_SHORT_EDGE}p`);
  });

  it('ขนาดที่อ่านไม่ได้ถือว่าไม่ผ่าน ไม่ใช่ผ่าน', () => {
    // จุดประสงค์ของเกณฑ์คือให้คนมาดูของที่ระบบไม่มั่นใจ
    // การปล่อยผ่านสิ่งที่วัดไม่ได้ทำให้เกณฑ์นี้ไม่มีความหมาย
    for (const [w, h] of [[0, 1080], [-5, 1080], [NaN, 1080], [1920, 0]]) {
      expect(checkDimensions(w, h).passed).toBe(false);
    }
  });
});
