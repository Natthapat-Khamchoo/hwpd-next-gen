import { describe, it, expect } from 'vitest';
import { chargeList, missingArrestFields, type ArrestFormState } from './arrestValidation';

const complete = (): ArrestFormState => ({
  team: ['ด.ต. ทดสอบ ระบบ'],
  chargeRows: [{ value: 'ยาเสพติดให้โทษประเภท 1', other: '' }],
  suspects: [{ name: 'นายทดสอบ ระบบหนึ่ง', idCard: '1234567890123', nat: 'ไทย', age: '32', address: '123 ม.1 อ.สามเงา จ.ตาก' }],
  f: {
    category: 'ยาเสพติด',
    arrestType: 'จับกุมซึ่งหน้า',
    warrantType: 'ไม่ใช่หมายจับ',
    warrantScope: 'ไม่ใช่หมายจับ',
    location: 'ทล.1 กม.571+500',
    lat: '16.416105',
    lng: '100.290527',
    items: 'ยาบ้า 200 เม็ด',
    circumstances: 'ตั้งจุดตรวจค้น พบของกลาง',
    forwarding: 'ส่ง พงส.สภ.สามเงา',
  },
});

describe('chargeList', () => {
  it('แปลงแถว "อื่นๆ" เป็นข้อความที่พิมพ์เอง', () => {
    expect(chargeList([{ value: '__OTHER__', other: '  ข้อหาเฉพาะทาง  ' }])).toEqual(['ข้อหาเฉพาะทาง']);
  });

  it('ตัดแถวที่ยังไม่ได้เลือกทิ้ง', () => {
    expect(chargeList([{ value: '', other: '' }, { value: 'เมาแล้วขับ', other: '' }])).toEqual(['เมาแล้วขับ']);
  });
});

describe('missingArrestFields', () => {
  it('ฟอร์มที่กรอกครบไม่มีช่องขาด', () => {
    expect(missingArrestFields(complete())).toEqual([]);
  });

  it('ไม่ปักหมุดแล้วบอกชื่อช่องพิกัด ไม่ใช่แค่ว่าข้อมูลไม่ครบ', () => {
    const state = complete();
    state.f.lat = '';
    state.f.lng = '';
    const missing = missingArrestFields(state);
    expect(missing).toHaveLength(1);
    expect(missing[0]).toContain('พิกัด');
  });

  it('ผู้ต้องหากรอกไม่ครบ บอกว่าคนที่เท่าไหร่และขาดช่องไหน', () => {
    const state = complete();
    state.suspects = [
      state.suspects[0],
      { name: 'นายทดสอบ ระบบสอง', idCard: '', nat: 'ไทย', age: '', address: 'ไม่ทราบ' },
    ];
    const missing = missingArrestFields(state);
    expect(missing).toHaveLength(1);
    expect(missing[0]).toContain('คนที่ 2');
    expect(missing[0]).toContain('เลขบัตร');
    expect(missing[0]).toContain('อายุ');
  });

  it('จับตามหมายต้องระบุขอบเขตหมาย', () => {
    const state = complete();
    state.f.arrestType = 'จับตามหมาย';
    const missing = missingArrestFields(state);
    expect(missing).toEqual([expect.stringContaining('ขอบเขตหมาย')]);
  });

  it('จับตามหมายที่ระบุขอบเขตแล้วผ่าน', () => {
    const state = complete();
    state.f.arrestType = 'จับตามหมาย';
    state.f.warrantScope = 'หมายใน (บช.ก.)';
    expect(missingArrestFields(state)).toEqual([]);
  });

  it('ฟอร์มเปล่ารายงานทุกช่องที่ขาดพร้อมกัน ไม่ใช่ทีละช่อง', () => {
    const missing = missingArrestFields({
      team: [''],
      chargeRows: [{ value: '', other: '' }],
      suspects: [{ name: '', idCard: '', nat: '', age: '', address: '' }],
      f: { arrestType: 'จับกุมซึ่งหน้า', warrantType: 'ไม่ใช่หมายจับ', warrantScope: 'ไม่ใช่หมายจับ' },
    });
    expect(missing.length).toBeGreaterThan(5);
    expect(missing).toEqual(expect.arrayContaining([expect.stringContaining('ชุดจับกุม')]));
    expect(missing).toEqual(expect.arrayContaining([expect.stringContaining('ข้อหา')]));
  });
});
