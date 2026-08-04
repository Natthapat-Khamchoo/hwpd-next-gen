import React from 'react';

/**
 * ช่องเลือกข้อหา สลับระหว่างจัดกลุ่มตาม พ.ร.บ. กับรายการเรียงยาวได้ (requirement ข้อ 14)
 *
 * ปุ่มสลับอยู่ที่หน้าเรียกใช้ ไม่ใช่ในนี้ เพราะฟอร์มหนึ่งใบมีช่องข้อหาได้หลายช่อง
 * (ตารางข้อหาของใบจับกุมและของผลการปฏิบัติ) การมีปุ่มสลับติดทุกช่องจะรกและสับสน
 * ว่าปุ่มไหนคุมช่องไหน
 *
 * ใช้ `<optgroup>` ของ HTML ไม่ได้ประดิษฐ์ dropdown เอง เพราะบนมือถือ ระบบปฏิบัติการ
 * จะแสดง select เป็นตัวเลือกเต็มจอที่คุ้นมืออยู่แล้ว ส่วน dropdown ที่เขียนเองจะเล็ก
 * และกดยากบนจอมือถือ ซึ่งเป็นอุปกรณ์หลักของเจ้าหน้าที่ในพื้นที่
 */

export interface ChargeGroup {
  group: string;
  charges: string[];
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  /** รายการแบบจัดกลุ่มแล้ว ใช้เมื่อ grouped = true */
  groups: ChargeGroup[];
  /** รายชื่อล้วน ใช้เมื่อ grouped = false หรือยังโหลดกลุ่มไม่ได้ */
  flat: string[];
  grouped: boolean;
  className?: string;
  /** เพิ่มตัวเลือก "อื่นๆ (พิมพ์ข้อหาเอง)" ท้ายรายการ */
  allowOther?: boolean;
  otherValue?: string;
}

export const ChargeSelect: React.FC<Props> = ({
  value,
  onChange,
  groups,
  flat,
  grouped,
  className = 'form-select border-warning',
  allowOther = false,
  otherValue = '__OTHER__',
}) => {
  // ยังโหลดกลุ่มไม่สำเร็จก็ยังต้องเลือกข้อหาได้ ตกกลับไปรายการเรียงยาวแทนช่องว่าง
  const useGroups = grouped && groups.length > 0;

  return (
    <select className={className} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">-- เลือกข้อหา --</option>
      {useGroups
        ? groups.map((g) => (
            <optgroup key={g.group} label={g.group}>
              {g.charges.map((ch) => (
                <option key={ch} value={ch}>{ch}</option>
              ))}
            </optgroup>
          ))
        : flat.map((ch) => (
            <option key={ch} value={ch}>{ch}</option>
          ))}
      {allowOther && <option value={otherValue}>อื่นๆ (พิมพ์ข้อหาเอง)</option>}
    </select>
  );
};

/** ปุ่มสลับเปิด/ปิดการจัดกลุ่ม วางไว้เหนือตารางข้อหา */
export const ChargeGroupToggle: React.FC<{ grouped: boolean; onToggle: () => void; disabled?: boolean }> = ({
  grouped,
  onToggle,
  disabled,
}) => (
  <button
    type="button"
    className={`btn btn-sm ${grouped ? 'btn-outline-info' : 'btn-outline-secondary'}`}
    onClick={onToggle}
    disabled={disabled}
    title={grouped ? 'ปิดการจัดกลุ่ม แสดงเป็นรายการเรียงยาว' : 'จัดกลุ่มข้อหาตาม พ.ร.บ.'}
  >
    <i className={`fa-solid ${grouped ? 'fa-layer-group' : 'fa-list'}`}></i>{' '}
    {grouped ? 'จัดกลุ่มตาม พ.ร.บ.' : 'รายการทั้งหมด'}
  </button>
);
