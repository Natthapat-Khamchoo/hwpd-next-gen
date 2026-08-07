import React, { Suspense, lazy } from 'react';

/**
 * โหลดแผนที่ด่านทั่วประเทศเมื่อเปิดหน้าภาพรวมจริง ๆ เท่านั้น
 *
 * หน้าแรกของ ผบก. คือ HWPD DASHBOARD ไม่ใช่หน้านี้ ถ้า import ตรง ๆ เบราว์เซอร์จะ
 * ดึง leaflet มาทุกครั้งที่ล็อกอินทั้งที่ยังไม่ได้เปิดแผนที่
 */
const NationalCheckpointMap = lazy(() =>
  import('./NationalCheckpointMap').then((m) => ({ default: m.NationalCheckpointMap })),
);

export const NationalCheckpointMapLazy: React.FC = () => (
  <Suspense
    fallback={
      <div className="glass-card d-flex align-items-center justify-content-center mb-4" style={{ minHeight: 460 }}>
        <span className="spinner-border text-warning me-2"></span>
        <span className="text-white-50">กำลังโหลดแผนที่จุดตั้งด่าน...</span>
      </div>
    }
  >
    <NationalCheckpointMap />
  </Suspense>
);
