import React, { useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { downloadSheet } from './excel';
import { PanelState, recentStart, today } from './panelHelpers';

/**
 * ระบบสืบค้นฐานข้อมูล (พอร์ตจาก loadHqView('search'))
 *
 * ตัวเดียวกับ "แกะรอยผลงาน" ของผู้กำกับการ ต่างกันแค่ที่นี่ฝังเป็นหน้า ไม่ใช่ modal
 * ยิงเฉพาะตอนกดค้นหา หน้านี้เปิดค้างไว้ได้ทั้งวันโดยไม่กินโควตาอ่านของ Google
 */

export const SearchPanel: React.FC<{ station: string }> = ({ station }) => {
  const { user } = useAuth();
  const [keyword, setKeyword] = useState('');
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    if (!keyword.trim()) return setError('กรุณาระบุคำค้นหา');
    setError('');
    setBusy(true);
    setRows(null);
    const res = await api.deepSearch('division', { keyword, start, end, station }, user?.token);
    setBusy(false);
    if (res.status !== 'success') return setError(res.message || 'ค้นหาไม่สำเร็จ');
    setRows(res.data || []);
  };

  /** ทุกฟิลด์ของแถวที่ค้นเจอ — ของเดิมมีปุ่ม "ตรวจสอบ" ต่อแถวเพื่อการนี้ */
  const showRecord = (row: any) => {
    const skip = new Set(['matches', 'dateMs']);
    const body = Object.entries(row)
      .filter(([k, v]) => !skip.has(k) && v !== '' && v !== null && v !== undefined)
      .map(([k, v]) => '<tr><td style="text-align:left;color:#9ca3af;white-space:nowrap;padding-right:12px">' +
        k + '</td><td style="text-align:left">' + String(v) + '</td></tr>')
      .join('');
    Swal.fire({
      title: row.type || 'รายละเอียด',
      width: 720,
      html: '<table style="width:100%;font-size:.85rem;border-collapse:collapse"><tbody>' + body + '</tbody></table>' +
        '<div style="margin-top:12px;text-align:left;font-size:.8rem;color:#9ca3af">ข้อความที่ตรงกับคำค้น:<br>' +
        (row.matches || []).join('<br>') + '</div>',
      confirmButtonText: 'ปิด',
    });
  };

  const exportExcel = () => {
    if (!rows || !rows.length) return;
    downloadSheet('ผลค้นหา_' + start + '_' + end, [
      ['ผลการค้นหา "' + keyword + '" ช่วงวันที่ ' + start + ' ถึง ' + end],
      [],
      ['วันที่', 'ประเภท', 'สถานี', 'หน่วย', 'ผู้บันทึก', 'ข้อความที่ตรง'],
      ...rows.map((r) => [r.date, r.type, r.station, r.unit, r.actionBy, (r.matches || []).join(' | ')]),
    ], 'ผลการค้นหา');
  };

  return (
    <div className="glass-card">
      <h5 className="text-white mb-1"><i className="fa-solid fa-magnifying-glass text-info"></i> สืบค้นฐานข้อมูลกองกำกับการ</h5>
      <p className="text-white-50 small mb-3">ค้นข้ามทุกตารางรายงานในกองกำกับการเดียวกัน</p>

      <div className="d-flex flex-column flex-md-row gap-2 mb-3">
        <input className="form-control bg-dark text-white border-secondary"
               placeholder="ชื่อเจ้าหน้าที่ / สถานที่ / ทะเบียนรถ / เลขคดี / ข้อหา"
               value={keyword} onChange={(e) => setKeyword(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && run()} />
        <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 170 }}
               value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 170 }}
               value={end} onChange={(e) => setEnd(e.target.value)} />
        <button className="btn btn-info fw-bold px-4" onClick={run} disabled={busy}>
          {busy ? 'กำลังค้น...' : 'ค้นหา'}
        </button>
      </div>

      <PanelState busy={busy} error={error} empty={false} emptyText="" />

      {rows && !busy && (
        <>
          <div className="d-flex justify-content-between align-items-center mb-2">
            <p className="text-white-50 small m-0">พบ {rows.length} รายการ{rows.length >= 300 && ' (แสดงสูงสุด 300)'}</p>
            <button className="btn btn-sm btn-success fw-bold" onClick={exportExcel} disabled={!rows.length}>
              <i className="fa-solid fa-file-excel"></i> Export
            </button>
          </div>
          <div className="table-responsive" style={{ maxHeight: 520, overflowY: 'auto' }}>
            <table className="table table-hq table-bordered align-middle small mb-0">
              <thead>
                <tr><th>วันที่</th><th>ประเภท</th><th className="text-start">สถานี/หน่วย</th>
                    <th className="text-start">ผู้บันทึก</th><th className="text-start">ข้อความที่ตรง</th>
                    <th style={{ width: 80 }}>ตรวจสอบ</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.recordId}>
                    <td className="text-nowrap">{r.date || '-'}</td>
                    <td>{r.type}</td>
                    <td className="text-start text-white-50">{r.station} {r.unit}</td>
                    <td className="text-start text-white-50">{r.actionBy}</td>
                    <td className="text-start text-white-50" style={{ maxWidth: 420 }}>
                      {(r.matches || []).map((m: string, i: number) => <div key={i}>{m}</div>)}
                    </td>
                    <td>
                      <button className="btn btn-sm btn-outline-info py-0 px-2" onClick={() => showRecord(r)}>
                        <i className="fa-solid fa-eye"></i>
                      </button>
                    </td>
                  </tr>
                ))}
                {!rows.length && <tr><td colSpan={6} className="text-center text-white-50 py-4">ไม่พบรายการที่ตรงกับคำค้น</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
