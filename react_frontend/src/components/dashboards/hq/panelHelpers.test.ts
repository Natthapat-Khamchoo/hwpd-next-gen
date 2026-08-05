/**
 * ช่วงวันที่ตั้งต้นของทุกหน้า ฝอ.กก. ต้องอิงเวลาไทย ไม่ใช่ UTC
 *
 * `toISOString()` คืนวันที่ตาม UTC ไทยเร็วกว่าเจ็ดชั่วโมง ทุกเช้าตั้งแต่เที่ยงคืนถึง
 * เจ็ดโมงค่านี้จึงเป็น "เมื่อวาน" แล้วรายงานของเวรดึกหายไปจากหน้าจอทั้งที่ลงชีตแล้ว
 * เทสชุดนี้ตรึงเวลาไว้ที่ตีหนึ่งของไทย ซึ่งเป็นช่วงที่บั๊กเดิมโผล่
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { currentMonth, recentStart, today } from './panelHelpers';

/** 5 ส.ค. 2569 เวลา 01:00 น. ตามเวลาไทย = 4 ส.ค. 18:00 UTC */
const THAI_EARLY_MORNING = new Date('2026-08-04T18:00:00Z');

const freeze = (instant: Date) => {
  vi.useFakeTimers();
  vi.setSystemTime(instant);
  // ให้เครื่องที่รันเทสอยู่โซนไหนก็ได้ผลเดียวกัน
  vi.spyOn(Date.prototype, 'getTimezoneOffset').mockReturnValue(-420);
};

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('today()', () => {
  it('คืนวันที่ของไทย ไม่ใช่ของ UTC ในช่วงเช้ามืด', () => {
    freeze(THAI_EARLY_MORNING);
    expect(today()).toBe('2026-08-05');
  });

  it('ตอนกลางวันซึ่งสองโซนตรงกันอยู่แล้วต้องไม่เปลี่ยนไปจากเดิม', () => {
    freeze(new Date('2026-08-05T05:00:00Z')); // เที่ยงของไทย
    expect(today()).toBe('2026-08-05');
  });
});

describe('recentStart()', () => {
  it('ย้อนหลัง 29 วันจากวันที่ของไทย', () => {
    freeze(THAI_EARLY_MORNING);
    expect(recentStart()).toBe('2026-07-07');
  });

  it('ช่วงตั้งต้นต้องคร่อมถึงวันนี้เสมอ ไม่จบที่เมื่อวาน', () => {
    freeze(THAI_EARLY_MORNING);
    expect(recentStart() <= today()).toBe(true);
    expect(today()).toBe('2026-08-05');
  });
});

describe('currentMonth()', () => {
  it('เดือนต้องมาจากวันที่ของไทย ไม่ใช่ของ UTC', () => {
    // เที่ยงคืนครึ่งของวันที่ 1 ก.ย. ตามเวลาไทย ซึ่ง UTC ยังเป็น 31 ส.ค.
    freeze(new Date('2026-08-31T17:30:00Z'));
    expect(currentMonth()).toBe('2026-09');
  });
});
