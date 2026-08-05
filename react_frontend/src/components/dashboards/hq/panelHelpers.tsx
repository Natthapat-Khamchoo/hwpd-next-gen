import React from 'react';

/**
 * ชิ้นส่วนที่ทุกหน้าย่อยของ ฝอ.กก. ใช้ร่วมกัน
 *
 * แยกออกมาเพราะทั้งหกหน้ามีจังหวะเดียวกันหมด — เลือกช่วงวันที่ กดโหลด รอ แล้ว
 * แสดงตารางหรือบอกว่าไม่มีข้อมูล การเขียนซ้ำหกรอบทำให้แต่ละหน้าค่อย ๆ เพี้ยนจากกัน
 */

/**
 * วันที่วันนี้ตามเวลาไทย
 *
 * ห้ามใช้ `toISOString()` ตรง ๆ เพราะมันคืนวันที่ตาม UTC ไทยเร็วกว่า UTC เจ็ดชั่วโมง
 * ทุกเช้าตั้งแต่เที่ยงคืนถึงเจ็ดโมง ค่านี้จึงคืน "เมื่อวาน" ผลคือช่วงวันที่ตั้งต้นของ
 * ทุกหน้า ฝอ.กก. จบที่เมื่อวาน แล้วรายงานที่เวรดึกส่งเข้ามาระหว่างนั้นหายไปจากหน้าจอ
 * ทั้งที่ลงชีตเรียบร้อยแล้ว — ช่วงเวลาที่พังคือช่วงที่เวรดึกทำงานพอดี
 */
export const today = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
};

/**
 * วันเริ่มต้นของช่วงวันที่ตั้งต้น = ย้อนหลัง 30 วัน
 *
 * ของเดิมตั้งเป็นวันที่ 1 ของเดือน ซึ่งทำให้ทุกแดชบอร์ดว่างเปล่าในเช้าวันที่ 1 ของ
 * ทุกเดือน — ผู้ใช้อ่านว่า "ข้อมูลหาย" ไม่ใช่ "ยังไม่มีข้อมูลเดือนนี้" ย้อนหลัง 30 วัน
 * คร่อมรอยต่อเดือนได้ และยังเป็นช่วงที่ผู้บังคับบัญชาดูอยู่แล้วเป็นปกติ
 */
export const recentStart = () => {
  const d = new Date();
  d.setDate(d.getDate() - 29);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
};
export const currentMonth = () => today().slice(0, 7);

export const num = (value: unknown): string =>
  Number(value || 0).toLocaleString('th-TH', { maximumFractionDigits: 2 });

/** แถบสถานะหนึ่งบรรทัด ใช้แทนการเขียน if 3 ชั้นในทุกหน้า */
export const PanelState: React.FC<{ busy: boolean; error: string; empty: boolean; emptyText: string }> = ({
  busy,
  error,
  empty,
  emptyText,
}) => {
  if (busy) {
    return (
      <div className="text-center text-white-50 py-5">
        <span
          className="spin d-inline-block"
          style={{ width: 32, height: 32, border: '3px solid var(--neon-blue)', borderTopColor: 'transparent', borderRadius: '50%' }}
        />
        <div className="mt-3 small">กำลังโหลดข้อมูล...</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="alert alert-danger py-2 small mb-0">
        <i className="fa-solid fa-triangle-exclamation"></i> {error}
      </div>
    );
  }
  if (empty) {
    return (
      <div className="text-center text-white-50 py-5">
        <i className="fa-solid fa-inbox mb-2" style={{ fontSize: '2rem' }}></i>
        <div className="small">{emptyText}</div>
      </div>
    );
  }
  return null;
};

/** ช่วงวันที่ + ปุ่มโหลด ชุดเดียวกับที่หัวหน้า overview ใช้ */
export const RangePicker: React.FC<{
  start: string;
  end: string;
  onStart: (v: string) => void;
  onEnd: (v: string) => void;
  onLoad: () => void;
  busy?: boolean;
}> = ({ start, end, onStart, onEnd, onLoad, busy }) => (
  <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
    <input type="date" className="form-control form-control-sm bg-dark text-white border-info" style={{ width: 155 }}
           value={start} onChange={(e) => onStart(e.target.value)} />
    <span className="text-white-50">ถึง</span>
    <input type="date" className="form-control form-control-sm bg-dark text-white border-info" style={{ width: 155 }}
           value={end} onChange={(e) => onEnd(e.target.value)} />
    <button className="btn btn-info btn-sm fw-bold" onClick={onLoad} disabled={busy}>
      <i className="fa-solid fa-rotate"></i> โหลดข้อมูล
    </button>
  </div>
);
