import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { ThaiDateInput } from './ThaiDateInput';

/**
 * ThaiDateInput แยกทางเดินตามอุปกรณ์ตั้งแต่ render แรก แล้วจำไว้ใน useRef
 * เทสจึงต้องตั้ง matchMedia ให้เสร็จ *ก่อน* render ไม่ใช่หลัง
 *
 * ทางฝั่งมือถือไม่เคยถูกรันเลยตอนไล่ทดสอบด้วยเบราว์เซอร์ เพราะหน้าต่าง Chrome
 * ที่ automation ใช้ย่อลงต่ำกว่า 769px ไม่ได้ จึงคุมด้วยเทสตัวนี้แทน
 */
const setViewport = (opts: { wide: boolean; coarse: boolean }) => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('min-width') ? opts.wide : opts.coarse,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
};

/** ช่องภาษาไทยที่ flatpickr สร้างขึ้น คือ .form-control ที่ไม่ใช่ input ต้นทางของเรา */
const thaiField = () =>
  document.querySelector('input.form-control:not(.flatpickr-input)') as HTMLInputElement;

describe('ThaiDateInput', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('มือถือ / จอแคบ', () => {
    beforeEach(() => setViewport({ wide: false, coarse: true }));

    it('ใช้ input ของระบบ ไม่ใช่ปฏิทิน flatpickr', () => {
      render(<ThaiDateInput id="d" type="date" value="2026-08-04" onChange={() => {}} />);
      const input = document.getElementById('d') as HTMLInputElement;

      expect(input.type).toBe('date');
      expect(input.value).toBe('2026-08-04');
      // flatpickr สร้างช่องภาษาไทยเพิ่มอีกช่อง ถ้ามีแปลว่าหลุดไปทางเดสก์ท็อป
      expect(document.querySelectorAll('input')).toHaveLength(1);
    });

    it('ส่งค่า ISO กลับตอนผู้ใช้เปลี่ยนวัน', () => {
      const onChange = vi.fn();
      render(<ThaiDateInput id="d" type="date" value="" onChange={onChange} />);

      fireEvent.change(document.getElementById('d') as HTMLInputElement, { target: { value: '2026-08-04' } });

      expect(onChange).toHaveBeenLastCalledWith('2026-08-04');
    });

    it('รองรับชนิด datetime-local ด้วย', () => {
      render(<ThaiDateInput id="dt" type="datetime-local" value="2026-08-04T09:30" onChange={() => {}} />);
      const input = document.getElementById('dt') as HTMLInputElement;

      expect(input.type).toBe('datetime-local');
      expect(input.value).toBe('2026-08-04T09:30');
    });
  });

  describe('เดสก์ท็อป', () => {
    beforeEach(() => setViewport({ wide: true, coarse: false }));

    it('ซ่อนช่องเก็บค่า ISO ไว้ แล้วโชว์ช่องภาษาไทยแทน', () => {
      render(<ThaiDateInput id="d" type="date" value="2026-08-04" onChange={() => {}} />);
      const hidden = document.getElementById('d') as HTMLInputElement;

      // นี่คือบั๊ก "ขึ้นสองช่อง" ที่เคยเจอ ถ้า type กลับมาเป็น date เมื่อไหร่แปลว่าพังซ้ำ
      expect(hidden.type).toBe('hidden');
      expect(hidden.value).toBe('2026-08-04');

      // flatpickr แปะปฏิทินไว้ที่ body ด้วย ซึ่งมี input ช่องปีของมันเองอยู่
      // จึงต้องเจาะจงช่องที่รับคลาสของเราไป ไม่ใช่กวาด input ทั้งหน้า
      expect(thaiField().value).toBe('4 ส.ค. 69');
    });

    it('แสดงปี พ.ศ. และเวลาแบบ 24 ชั่วโมงในชนิด datetime-local', () => {
      render(<ThaiDateInput id="dt" type="datetime-local" value="2026-08-04T21:05" onChange={() => {}} />);

      expect(thaiField().value).toBe('4 ส.ค. 69 21:05 น.');
    });

    it('ตามค่าที่ฟอร์มเปลี่ยนจากข้างนอก เช่นปุ่ม "เวลาปัจจุบัน"', () => {
      const { rerender } = render(<ThaiDateInput id="d" type="date" value="2026-08-04" onChange={() => {}} />);
      rerender(<ThaiDateInput id="d" type="date" value="2026-12-25" onChange={() => {}} />);

      expect(thaiField().value).toBe('25 ธ.ค. 69');
    });

    it('ยังซ่อนอยู่หลัง re-render ที่ไม่ได้เปลี่ยนค่า (บั๊ก dropdown โหลดเสร็จ)', () => {
      const { rerender } = render(<ThaiDateInput id="d" type="date" value="2026-08-04" onChange={() => {}} />);
      // จำลองรอบ re-render ที่ useStationData ทำให้เกิดตอนโหลด dropdown เสร็จ
      rerender(<ThaiDateInput id="d" type="date" value="2026-08-04" onChange={() => {}} />);

      expect((document.getElementById('d') as HTMLInputElement).type).toBe('hidden');
    });
  });
});
