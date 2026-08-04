import React from 'react';

/**
 * แถบบอกว่าฟอร์มนี้กู้ค่าที่กรอกค้างไว้กลับมาให้แล้ว พร้อมปุ่มล้างทิ้ง
 *
 * ต้องมีปุ่มล้าง เพราะการกู้ค่าอัตโนมัติโดยไม่บอกจะทำให้เจ้าหน้าที่ที่ตั้งใจกรอกใบใหม่
 * เผลอส่งค่าของใบก่อนหน้าไปโดยไม่ทันสังเกต ซึ่งอันตรายกว่าการที่ข้อมูลหาย
 *
 * ใช้สไตล์ alert เดียวกับที่หน้าประวัติการส่งใช้อยู่ ไม่ได้ประดิษฐ์หน้าตาใหม่
 */
export const DraftNotice: React.FC<{ onClear: () => void }> = ({ onClear }) => (
  <div
    className="alert small mb-3 d-flex justify-content-between align-items-center gap-2"
    style={{
      background: 'rgba(255, 193, 7, 0.08)',
      border: '1px solid rgba(255, 193, 7, 0.3)',
      color: '#e2e8f0',
      borderRadius: 8,
    }}
  >
    <span>
      <i className="fa-solid fa-clock-rotate-left text-warning"></i> กู้ข้อมูลที่กรอกค้างไว้กลับมาให้แล้ว
      ตรวจสอบความถูกต้องก่อนส่ง
    </span>
    <button type="button" className="btn btn-sm btn-outline-warning flex-shrink-0" onClick={onClear}>
      ล้างแล้วเริ่มใหม่
    </button>
  </div>
);
