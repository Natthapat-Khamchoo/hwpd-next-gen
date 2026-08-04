import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ChargeGroupToggle, ChargeSelect } from './ChargeSelect';

/**
 * ช่องเลือกข้อหาแบบจัดกลุ่ม (requirement ข้อ 14)
 *
 * เทสระดับ component เพราะตรรกะที่สำคัญคือ "เมื่อไหร่ที่ตกกลับไปใช้รายการเรียงยาว"
 * ซึ่งเป็นเส้นทางที่ผู้ใช้จะเจอจริงเมื่อโหลดกลุ่มไม่สำเร็จ และเป็นเส้นทางที่คนเขียน
 * มักลืมทดสอบเพราะปกติ API ตอบสำเร็จ
 */

const GROUPS = [
  { group: 'พ.ร.บ.ทางหลวง', charges: ['บรรทุกน้ำหนักเกินอัตรา'] },
  { group: 'พ.ร.บ.จราจรทางบก', charges: ['ขับรถเร็วเกินกำหนด', 'เมาแล้วขับ'] },
];
const FLAT = ['บรรทุกน้ำหนักเกินอัตรา', 'ขับรถเร็วเกินกำหนด', 'เมาแล้วขับ'];

const renderSelect = (props: Partial<React.ComponentProps<typeof ChargeSelect>> = {}) =>
  render(
    <ChargeSelect
      value=""
      onChange={() => {}}
      groups={GROUPS}
      flat={FLAT}
      grouped
      {...props}
    />,
  );

describe('ChargeSelect', () => {
  it('แสดงเป็นกลุ่มตาม พ.ร.บ. เมื่อเปิดการจัดกลุ่ม', () => {
    const { container } = renderSelect();
    const labels = [...container.querySelectorAll('optgroup')].map((g) => g.label);
    expect(labels).toEqual(['พ.ร.บ.ทางหลวง', 'พ.ร.บ.จราจรทางบก']);
  });

  it('แสดงเป็นรายการเรียงยาวเมื่อปิดการจัดกลุ่ม', () => {
    const { container } = renderSelect({ grouped: false });
    expect(container.querySelectorAll('optgroup')).toHaveLength(0);
    expect(container.querySelectorAll('option')).toHaveLength(FLAT.length + 1);   // + "-- เลือกข้อหา --"
  });

  it('ตกกลับไปใช้รายการเรียงยาวเมื่อยังโหลดกลุ่มไม่สำเร็จ', () => {
    // ยังต้องเลือกข้อหาได้ ไม่ใช่เจอช่องว่างเปล่า
    const { container } = renderSelect({ groups: [] });
    expect(container.querySelectorAll('optgroup')).toHaveLength(0);
    expect(screen.getByRole('option', { name: 'เมาแล้วขับ' })).toBeDefined();
  });

  it('เพิ่มตัวเลือก "อื่นๆ" เฉพาะเมื่อสั่งให้เพิ่ม', () => {
    renderSelect({ allowOther: true });
    expect(screen.getByRole('option', { name: 'อื่นๆ (พิมพ์ข้อหาเอง)' })).toBeDefined();
  });

  it('ไม่มีตัวเลือก "อื่นๆ" เป็นค่าเริ่มต้น', () => {
    renderSelect();
    expect(screen.queryByRole('option', { name: 'อื่นๆ (พิมพ์ข้อหาเอง)' })).toBeNull();
  });

  it('ส่งค่าที่เลือกกลับไปให้ผู้เรียก', () => {
    const onChange = vi.fn();
    const { container } = renderSelect({ onChange });
    fireEvent.change(container.querySelector('select')!, { target: { value: 'เมาแล้วขับ' } });
    expect(onChange).toHaveBeenCalledWith('เมาแล้วขับ');
  });
});

describe('ChargeGroupToggle', () => {
  it('ป้ายปุ่มบอกสถานะปัจจุบัน', () => {
    const { rerender } = render(<ChargeGroupToggle grouped onToggle={() => {}} />);
    expect(screen.getByRole('button').textContent).toContain('จัดกลุ่มตาม พ.ร.บ.');

    rerender(<ChargeGroupToggle grouped={false} onToggle={() => {}} />);
    expect(screen.getByRole('button').textContent).toContain('รายการทั้งหมด');
  });

  it('ปิดปุ่มเมื่อยังไม่มีข้อมูลกลุ่มให้สลับ', () => {
    render(<ChargeGroupToggle grouped onToggle={() => {}} disabled />);
    expect(screen.getByRole('button')).toHaveProperty('disabled', true);
  });
});
