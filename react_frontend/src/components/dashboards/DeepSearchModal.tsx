import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';

/**
 * ค้นหาเชิงลึก — ใช้ร่วมกันสองที่
 *
 *   scope="division"  ปุ่ม "แกะรอยผลงาน" ของผู้กำกับการ ค้นในกองตัวเอง
 *   scope="national"  ปุ่ม "ค้นหาทุกกอง" ของ ผบก. ค้นข้ามทั้ง 8 กก.
 *
 * ยิงเฉพาะตอนกดค้นหาเท่านั้น ระดับประเทศต้องเปิด 8 สเปรดชีต x 7 ตาราง ถ้าโหลดเอง
 * ตอนเปิดหน้าจะชนโควตาการอ่านของ Google ทันทีที่มีคนเปิดพร้อมกันสองคน
 */

interface Props {
  scope: 'division' | 'national';
  station?: string;
  onClose: () => void;
}

const firstOfMonth = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0]; };
const today = () => new Date().toISOString().split('T')[0];

export const DeepSearchModal: React.FC<Props> = ({ scope, station, onClose }) => {
  const { user } = useAuth();
  const [keyword, setKeyword] = useState('');
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const run = async () => {
    if (!keyword.trim()) return setErr('กรุณาระบุคำค้นหา');
    setErr(''); setBusy(true); setRows(null);
    const res = await api.deepSearch(scope, { keyword, start, end, station }, user?.token);
    setBusy(false);
    if (res.status !== 'success') return setErr(res.message || 'ค้นหาไม่สำเร็จ');
    setRows(res.data || []);
  };

  return (
    <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-start justify-content-center"
         style={{ background: 'rgba(0,0,0,.75)', zIndex: 2000, overflowY: 'auto', padding: '3vh 1rem' }}>
      <div className="glass-card p-4" style={{ maxWidth: 960, width: '100%' }}>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="text-white m-0">
            <i className="fa-solid fa-user-secret text-info"></i>{' '}
            {scope === 'national' ? 'ค้นหาทุกกองกำกับการ' : 'แกะรอยผลงานในกองกำกับ'}
          </h5>
          <button className="btn btn-sm btn-outline-light" onClick={onClose}>ปิด</button>
        </div>

        <div className="d-flex flex-column flex-md-row gap-2 mb-3">
          <input className="form-control bg-dark text-white border-secondary"
                 placeholder="ชื่อเจ้าหน้าที่ / สถานที่ / ทะเบียน / เลขคดี"
                 value={keyword} onChange={(e) => setKeyword(e.target.value)}
                 onKeyDown={(e) => e.key === 'Enter' && run()} />
          <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 160 }}
                 value={start} onChange={(e) => setStart(e.target.value)} />
          <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 160 }}
                 value={end} onChange={(e) => setEnd(e.target.value)} />
          <button className="btn btn-info fw-bold px-4" onClick={run} disabled={busy}>
            {busy ? 'กำลังค้น...' : 'ค้นหา'}
          </button>
        </div>

        {err && <div className="alert alert-warning py-2">{err}</div>}
        {busy && scope === 'national' && (
          <p className="text-white-50 small">ค้นข้ามทั้ง 8 กองกำกับการ อาจใช้เวลาสักครู่</p>
        )}

        {rows && (
          <>
            <p className="text-white-50 small mb-2">พบ {rows.length} รายการ{rows.length >= 300 && ' (แสดงสูงสุด 300)'}</p>
            <div className="table-responsive" style={{ maxHeight: '55vh' }}>
              <table className="table table-sc table-bordered align-middle small">
                <thead>
                  <tr>
                    <th>วันที่</th>
                    {scope === 'national' && <th>กก.</th>}
                    <th>ประเภท</th><th>สถานี/หน่วย</th><th>ผู้บันทึก</th><th className="text-start">ข้อความที่ตรง</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.recordId}>
                      <td className="text-nowrap">{r.date || '-'}</td>
                      {scope === 'national' && <td>{r.divName}</td>}
                      <td>{r.type}</td>
                      <td className="text-white-50">{r.station} {r.unit}</td>
                      <td className="text-white-50">{r.actionBy}</td>
                      <td className="text-start text-white-50" style={{ maxWidth: 380 }}>
                        {(r.matches || []).map((m: string, i: number) => <div key={i}>{m}</div>)}
                      </td>
                    </tr>
                  ))}
                  {!rows.length && <tr><td colSpan={scope === 'national' ? 6 : 5} className="text-center text-white-50 py-4">ไม่พบรายการที่ตรงกับคำค้น</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
