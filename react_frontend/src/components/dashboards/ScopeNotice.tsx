import React from 'react';

/**
 * บอกให้ชัดว่าตัวเลขบนหน้านี้เป็นของ กก. ไหน (requirement ข้อ 3)
 *
 * ตั้งแต่ข้อ 3 เป็นต้นไป ภาพรวมของ บก.ทล. นับเฉพาะ กก.8 ส่วน กก.1-7 ยังถูกรวมยอด
 * และเก็บครบทุกวัน แต่ไม่ถูกนำขึ้นหน้านี้ **ถ้าไม่บอก ผู้บังคับบัญชาจะอ่านตัวเลข
 * ของ กก.8 ว่าเป็นยอดทั้งประเทศ** ซึ่งผิดทันทีและเป็นความผิดพลาดที่มองไม่เห็นด้วยตา
 */

interface Props {
  /** เลข กก. ที่หน้านี้นับ เช่น "8" */
  dashboardDivision?: string;
  /** เลข กก. ที่มีข้อมูลเก็บไว้แต่ไม่ถูกนับ */
  archivedDivisions?: string[];
  /** กำลังแสดงข้อมูลสำรองรวมด้วยอยู่หรือไม่ */
  includesArchived?: boolean;
  onToggleArchived?: () => void;
}

export const ScopeNotice: React.FC<Props> = ({
  dashboardDivision,
  archivedDivisions = [],
  includesArchived,
  onToggleArchived,
}) => {
  if (!dashboardDivision && !archivedDivisions.length) return null;

  return (
    <div
      className="alert d-flex flex-wrap align-items-center gap-2 py-2 mb-4 small"
      style={{
        background: 'rgba(255, 193, 7, 0.08)',
        border: '1px solid rgba(255, 193, 7, 0.3)',
        color: '#e2e8f0',
        borderRadius: 8,
      }}
    >
      <i className="fa-solid fa-circle-info text-warning"></i>
      {includesArchived ? (
        <span>
          กำลังแสดง<b className="text-warning"> ข้อมูลสำรองของทุกกองกำกับการ </b>
          ซึ่งไม่ใช่ตัวเลขที่ใช้รายงานตามปกติ
        </span>
      ) : (
        <span>
          ตัวเลขทั้งหมดบนหน้านี้เป็นของ <b className="text-warning">กก.{dashboardDivision}</b> เท่านั้น
          {archivedDivisions.length > 0 && (
            <> ส่วน กก.{archivedDivisions.join(', ')} ยังเก็บข้อมูลไว้ครบแต่ไม่นับรวมในภาพรวมนี้</>
          )}
        </span>
      )}
      {onToggleArchived && archivedDivisions.length > 0 && (
        <button type="button" className="btn btn-sm btn-outline-warning ms-auto" onClick={onToggleArchived}>
          {includesArchived ? `กลับไปดูเฉพาะ กก.${dashboardDivision}` : 'ดูข้อมูลสำรองทุกกอง'}
        </button>
      )}
    </div>
  );
};
