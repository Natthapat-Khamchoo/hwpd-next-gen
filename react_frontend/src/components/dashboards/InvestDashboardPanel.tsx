import React, { useEffect, useRef, useState } from 'react';

/**
 * ฝังแดชบอร์ดงานสืบสวน (คนละแอป คนละโดเมน) ไว้ในหน้า ผบก.
 *
 * ปลายทางตั้ง CSP ไว้ว่า
 *   Content-Security-Policy: frame-ancestors 'self' https://hwpd-next-gen.vercel.app
 *
 * โดเมนที่ใช้งานจริงตอนนี้คือ hwpd-next-gen2.vercel.app ซึ่งไม่อยู่ในรายการนั้น
 * เบราว์เซอร์จะบล็อกการฝังแบบเงียบ ๆ — ได้กรอบเปล่า ไม่มี error ให้ผู้ใช้เห็น
 * จึงต้องตรวจเองว่าโหลดไม่ขึ้นแล้วบอกให้ชัดพร้อมทางออก ไม่ปล่อยให้เห็นพื้นที่ว่าง
 *
 * ขนาด 125% + scale(0.8) ยกมาจากของเดิม (commit eb9c1c4) แก้ปัญหาเนื้อหาล้นกรอบ
 */

const SRC = 'https://hwpd-invest-dashboard.vercel.app/?tab=result';

// ถ้าเกินเวลานี้แล้ว onLoad ยังไม่ยิง ถือว่าถูกบล็อก
const LOAD_TIMEOUT_MS = 6000;

export const InvestDashboardPanel: React.FC = () => {
  const [state, setState] = useState<'loading' | 'ready' | 'blocked'>('loading');
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    timer.current = window.setTimeout(() => {
      setState((s) => (s === 'loading' ? 'blocked' : s));
    }, LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(timer.current);
  }, []);

  return (
    <div className="glass-card w-100 p-0 overflow-hidden" style={{ minHeight: '70vh' }}>
      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 px-3 py-2 border-bottom border-secondary">
        <h5 className="text-white m-0">
          <i className="fa-solid fa-magnifying-glass-chart text-warning"></i> แดชบอร์ดงานสืบสวน
        </h5>
        <a className="btn btn-sm btn-outline-warning" href={SRC} target="_blank" rel="noreferrer">
          <i className="fa-solid fa-arrow-up-right-from-square"></i> เปิดในแท็บใหม่
        </a>
      </div>

      {state === 'blocked' ? (
        <div className="p-4 text-center" style={{ minHeight: '60vh' }}>
          <i className="fa-solid fa-shield-halved text-warning mb-3" style={{ fontSize: '2.5rem' }}></i>
          <h6 className="text-white">ฝังหน้านี้ไม่ได้จากโดเมนปัจจุบัน</h6>
          <p className="text-white-50 small mb-3">
            แดชบอร์ดงานสืบสวนอนุญาตให้ฝังได้เฉพาะจาก <code>hwpd-next-gen.vercel.app</code><br />
            แต่ระบบนี้เปิดอยู่ที่โดเมนอื่น เบราว์เซอร์จึงบล็อกไว้
          </p>
          <p className="text-white-50 small mb-3">
            แก้ได้โดยเพิ่มโดเมนของระบบนี้ลงใน <code>frame-ancestors</code> ของโปรเจกต์
            <code> hwpd-invest-dashboard</code> ระหว่างนี้กดปุ่มด้านบนเปิดในแท็บใหม่ได้ตามปกติ
          </p>
          <a className="btn btn-warning fw-bold" href={SRC} target="_blank" rel="noreferrer">
            เปิดแดชบอร์ดงานสืบสวน
          </a>
        </div>
      ) : (
        <div className="position-relative w-100" style={{ height: '72vh', overflow: 'hidden' }}>
          {state === 'loading' && (
            <div className="position-absolute top-50 start-50 translate-middle text-white-50 small" style={{ zIndex: 2 }}>
              กำลังโหลดแดชบอร์ดงานสืบสวน...
            </div>
          )}
          <iframe
            src={SRC}
            title="บก.ทล. แดชบอร์ดงานสืบสวน"
            className="position-absolute"
            style={{
              border: 'none',
              background: 'transparent',
              zIndex: 1,
              width: '125%',
              height: '125%',
              transform: 'scale(0.8)',
              transformOrigin: 'top left',
              top: 0,
              left: 0,
            }}
            onLoad={() => { window.clearTimeout(timer.current); setState('ready'); }}
            allowFullScreen
          />
        </div>
      )}
    </div>
  );
};
