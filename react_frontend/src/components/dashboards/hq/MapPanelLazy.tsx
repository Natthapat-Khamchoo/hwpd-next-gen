import React, { Suspense, lazy } from 'react';

/**
 * โหลด `MapPanel` เมื่อผู้ใช้กดเข้าเมนูแผนที่จริง ๆ เท่านั้น
 *
 * ถ้า import ตรง ๆ ในแผงควบคุม เบราว์เซอร์จะดึง leaflet (152 KB) มาพร้อมหน้า ฝอ.
 * ทุกครั้งที่เปิด ทั้งที่คนส่วนใหญ่เข้ามาดูภาพรวมแล้วออก ไม่ได้แตะแผนที่เลย
 */
const MapPanel = lazy(() => import('./MapPanel').then((m) => ({ default: m.MapPanel })));

interface Props {
  station: string;
  stations?: { station: string; name: string }[];
}

export const MapPanelLazy: React.FC<Props> = (props) => (
  <Suspense
    fallback={
      <div className="glass-card d-flex align-items-center justify-content-center" style={{ minHeight: 420 }}>
        <span className="spinner-border text-info me-2"></span>
        <span className="text-white-50">กำลังโหลดแผนที่...</span>
      </div>
    }
  >
    <MapPanel {...props} />
  </Suspense>
);
