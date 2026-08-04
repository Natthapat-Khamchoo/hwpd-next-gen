import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { DRAFT_TTL_MS, purgeExpiredDrafts, useFormDraft } from './useFormDraft';

/**
 * คงค่าฟอร์มเมื่อย้อนกลับ (requirement ข้อ 12)
 *
 * ตรรกะนี้พังแบบเงียบได้สองทาง — ไม่เก็บเลย (ผู้ใช้เสียงานที่กรอก) หรือเก็บแล้ว
 * ไม่ล้าง (ผู้ใช้ส่งข้อมูลเก่าซ้ำโดยไม่รู้ตัว) ทางหลังอันตรายกว่า จึงเทสหนักที่ฝั่งล้าง
 */

const KEY = 'hwpd:draft:test51:demo';

const advance = async (ms: number) => {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
};

describe('useFormDraft', () => {
  it('เก็บค่าที่กรอกลง sessionStorage หลังหยุดพิมพ์', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));

    act(() => result.current[1]({ name: 'ทดสอบ' }));
    expect(sessionStorage.getItem(KEY)).toBeNull();   // ยังไม่ครบเวลา debounce

    await advance(600);
    expect(JSON.parse(sessionStorage.getItem(KEY)!).values.name).toBe('ทดสอบ');
    vi.useRealTimers();
  });

  it('ไม่เก็บร่างของฟอร์มที่ยังไม่มีใครกรอกอะไร', async () => {
    // ถ้าเก็บ ฟอร์มที่รีเซ็ตตัวเองหลังบันทึกสำเร็จจะทิ้งร่างเปล่าไว้
    // แล้วรอบหน้าจะขึ้นว่า "กู้ร่างคืนแล้ว" ทั้งที่ไม่มีอะไรกู้
    vi.useFakeTimers();
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));
    act(() => result.current[1]({ name: '' }));
    await advance(600);
    expect(sessionStorage.getItem(KEY)).toBeNull();
    vi.useRealTimers();
  });

  it('กู้ร่างกลับมาและติดธง restored เมื่อเปิดฟอร์มใหม่', () => {
    sessionStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), values: { name: 'ค้างไว้' } }));
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));
    expect(result.current[0].name).toBe('ค้างไว้');
    expect(result.current[2].restored).toBe(true);
  });

  it('เติมฟิลด์ใหม่ที่เพิ่มเข้ามาทีหลังให้ร่างเก่า', () => {
    // ฟอร์มอาจเพิ่มช่องใหม่หลังจากที่ผู้ใช้มีร่างค้างอยู่แล้ว ร่างเก่าต้องไม่ทำให้ช่องใหม่หาย
    sessionStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), values: { name: 'เก่า' } }));
    const { result } = renderHook(() => useFormDraft('demo', { name: '', phone: '0812345678' }, 'test51'));
    expect(result.current[0]).toEqual({ name: 'เก่า', phone: '0812345678' });
  });

  it('ร่างที่เป็น array ต้องกลับมาเป็น array ไม่ใช่ object', () => {
    // การ spread array เข้ากับ array ได้ object ที่มีคีย์เป็นตัวเลข ซึ่งทำให้ .map() พังทั้งฟอร์ม
    sessionStorage.setItem(
      'hwpd:draft:test51:rows',
      JSON.stringify({ savedAt: Date.now(), values: [{ name: 'ก' }, { name: 'ข' }] }),
    );
    const { result } = renderHook(() => useFormDraft('rows', [{ name: '' }], 'test51'));
    expect(Array.isArray(result.current[0])).toBe(true);
    expect(result.current[0]).toHaveLength(2);
  });

  it('ทิ้งร่างที่เก่ากว่า 24 ชั่วโมง', () => {
    sessionStorage.setItem(
      KEY,
      JSON.stringify({ savedAt: Date.now() - DRAFT_TTL_MS - 1000, values: { name: 'เมื่อวาน' } }),
    );
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));
    expect(result.current[0].name).toBe('');
    expect(result.current[2].restored).toBe(false);
  });

  it('clear() ลบร่างและปิดธง restored', () => {
    sessionStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), values: { name: 'ค้างไว้' } }));
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));

    act(() => result.current[2].clear());
    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(result.current[2].restored).toBe(false);
  });

  it('ร่างที่ค้างใน debounce ต้องไม่ถูกเขียนกลับหลังกด clear', async () => {
    // เคสจริง: กดส่งสำเร็จ -> clear() -> timer ที่ตั้งไว้ก่อนหน้าเด้ง -> ร่างกลับมา
    vi.useFakeTimers();
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));

    act(() => result.current[1]({ name: 'กำลังพิมพ์' }));
    act(() => result.current[2].clear());
    await advance(1000);

    expect(sessionStorage.getItem(KEY)).toBeNull();
    vi.useRealTimers();
  });

  it('แยกร่างตามบัญชีผู้ใช้', () => {
    // เครื่องในหน่วยใช้ร่วมกันหลายคน ร่างของคนก่อนหน้าต้องไม่โผล่มาให้คนที่ล็อกอินต่อ
    sessionStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), values: { name: 'ของ test51' } }));
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test52'));
    expect(result.current[0].name).toBe('');
  });

  it('purgeExpiredDrafts ล้างเฉพาะร่างที่หมดอายุ', () => {
    sessionStorage.setItem('hwpd:draft:a:x', JSON.stringify({ savedAt: Date.now(), values: {} }));
    sessionStorage.setItem('hwpd:draft:b:y', JSON.stringify({ savedAt: Date.now() - DRAFT_TTL_MS - 1, values: {} }));
    sessionStorage.setItem('ของคนอื่น', 'ห้ามแตะ');

    expect(purgeExpiredDrafts()).toBe(1);
    expect(sessionStorage.getItem('hwpd:draft:a:x')).not.toBeNull();
    expect(sessionStorage.getItem('hwpd:draft:b:y')).toBeNull();
    expect(sessionStorage.getItem('ของคนอื่น')).toBe('ห้ามแตะ');
  });

  it('ร่างที่พังอ่านไม่ออกถูกทิ้งแทนที่จะทำให้ฟอร์มล่ม', () => {
    sessionStorage.setItem(KEY, '{ ไม่ใช่ json');
    const { result } = renderHook(() => useFormDraft('demo', { name: '' }, 'test51'));
    expect(result.current[0].name).toBe('');
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
});
