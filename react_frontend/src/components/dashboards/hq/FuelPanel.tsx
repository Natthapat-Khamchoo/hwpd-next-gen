import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { downloadSheet } from './excel';
import { PanelState, currentMonth, num } from './panelHelpers';

/**
 * ระบบควบคุมโควตาน้ำมัน/น้ำมันเครื่อง (พอร์ตจาก loadHQFuelData)
 *
 * ตัวเลขที่ ฝอ. ต้องตอบผู้บังคับบัญชาคือ "เหลือเท่าไหร่" ไม่ใช่ "ใช้ไปเท่าไหร่" ตาราง
 * กับการ์ดจึงมีช่องคงเหลือทุกชุด และติดลบเมื่อไหร่ต้องเห็นเป็นสีแดงทันที
 *
 * ตั้งโควตาผ่าน modal ตามของเดิม ไม่ใช่ช่องกรอกฝังในตาราง เพราะเป็นงานที่ทำเดือนละ
 * ครั้ง การเปิดช่องกรอกค้างไว้ตลอดเวลาเสี่ยงพิมพ์ทับของจริงโดยไม่ตั้งใจ
 */

interface Row {
  name: string;
  quotaB: number;
  usedB: number;
  oilQuotaL: number;
  oilUsedL: number;
  usedL: number;
}

const pct = (used: number, quota: number) => (quota > 0 ? Math.min(100, (used / quota) * 100) : 0);
const barClass = (used: number, quota: number) =>
  quota > 0 && used > quota ? 'bg-danger' : quota > 0 && used / quota > 0.8 ? 'bg-warning' : 'bg-info';
const remainClass = (remain: number) => (remain < 0 ? 'text-danger fw-bold' : 'text-success');

export const FuelPanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState<Record<string, Row> | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [quotaOpen, setQuotaOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, { baht: string; oilLiters: string }>>({});

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqFuel(station, month, user?.token);
    if (res.status === 'success') {
      setSummary(res.data.summary);
      setLogs(res.data.logs || []);
    } else {
      setError(res.message || 'โหลดข้อมูลน้ำมันไม่สำเร็จ');
    }
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station, month]);

  const openQuota = () => {
    // เติมค่าที่บันทึกไว้แล้วลงในฟอร์ม ฝอ. จะได้แก้เฉพาะสถานีที่เปลี่ยน
    const next: Record<string, { baht: string; oilLiters: string }> = {};
    Object.entries(summary || {}).forEach(([id, row]) => {
      if (id !== 'total') next[id] = { baht: String(row.quotaB || ''), oilLiters: String(row.oilQuotaL || '') };
    });
    setDraft(next);
    setQuotaOpen(true);
  };

  const saveQuota = async () => {
    setSaving(true);
    const res = await api.hqSaveFuelQuota(
      {
        stationId: station,
        monthYear: month,
        quotas: Object.entries(draft).map(([stationId, v]) => ({
          stationId,
          baht: Number(v.baht) || 0,
          oilLiters: Number(v.oilLiters) || 0,
        })),
      },
      user?.token,
    );
    setSaving(false);
    if (res.status === 'success') {
      setQuotaOpen(false);
      await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const rows = Object.entries(summary || {}).filter(([id]) => id !== 'total');
  const total = summary?.total;

  const exportSummary = () => {
    downloadSheet(`สรุปน้ำมัน_${month}`, [
      [`สรุปการใช้น้ำมันและน้ำมันเครื่อง ประจำเดือน ${month}`],
      [],
      ['สถานี', 'ใช้เชื้อเพลิง (ลิตร)', 'โควตาเชื้อเพลิง (บาท)', 'ใช้ไป (บาท)', 'คงเหลือ (บาท)',
       'โควตาน้ำมันเครื่อง (ลิตร)', 'ใช้ไป (ลิตร)', 'คงเหลือ (ลิตร)'],
      ...rows.map(([, r]) => [
        r.name, r.usedL, r.quotaB, r.usedB, r.quotaB - r.usedB,
        r.oilQuotaL, r.oilUsedL, r.oilQuotaL - r.oilUsedL,
      ]),
      ...(total ? [['รวมทั้ง กก.', total.usedL, total.quotaB, total.usedB, total.quotaB - total.usedB,
                    total.oilQuotaL, total.oilUsedL, total.oilQuotaL - total.oilUsedL]] : []),
    ], 'สรุปยอด');
  };

  const exportLogs = () => {
    downloadSheet(`ประวัติน้ำมันรายคัน_${month}`, [
      [`ประวัติการทำรายการน้ำมัน ประจำเดือน ${month}`],
      [],
      ['วัน/เวลา', 'สถานี', 'หน่วย', 'ผู้ดำเนินการ', 'ทะเบียนรถ', 'รายการ',
       'เลขไมล์ปัจจุบัน', 'เลขไมล์ครั้งก่อน', 'ระยะทาง (กม.)', 'จำนวนลิตร', 'ประเภท', 'จำนวนเงิน', 'เลขที่ใบเสร็จ'],
      ...logs.map((l) => [
        l.date, l.station, l.unit, l.person, l.car, l.type,
        l.currentMileage, l.prevMileage, l.distance, l.liters, l.fuelType,
        l.type === 'เติมน้ำมัน' ? l.baht : '', l.receipt,
      ]),
    ], 'ประวัติรายคัน');
  };

  const kpi = (label: string, value: string, cls: string) => (
    <div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}>
      <div className="title">{label}</div><div className={`value ${cls}`}>{value}</div>
    </div>
  );

  return (
    <>
      <div className="glass-card mb-4">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 border-bottom border-secondary pb-3 mb-4">
          <h5 className="text-white m-0"><i className="fa-solid fa-gas-pump text-warning"></i> ระบบควบคุมโควตาน้ำมัน/น้ำมันเครื่อง</h5>
          {canEdit && (
            <button className="btn btn-warning fw-bold" onClick={openQuota} disabled={busy || !rows.length}>
              <i className="fa-solid fa-sliders"></i> ตั้งค่าโควตาประจำเดือน
            </button>
          )}
        </div>

        <div className="row g-3 align-items-end mb-4">
          <div className="col-12 col-md-4">
            <label className="form-label small text-info">เลือกเดือนที่ต้องการดูข้อมูล</label>
            <input type="month" className="form-control bg-dark text-white border-warning"
                   value={month} onChange={(e) => setMonth(e.target.value)} />
          </div>
          <div className="col-12 col-md-8 text-md-end">
            <button className="btn btn-outline-info fw-bold me-2" onClick={exportLogs} disabled={!logs.length}>
              <i className="fa-solid fa-list-check"></i> ส่งออกประวัติรายคัน
            </button>
            <button className="btn btn-success fw-bold" onClick={exportSummary} disabled={!rows.length}>
              <i className="fa-solid fa-file-excel"></i> ส่งออกสรุปยอด
            </button>
          </div>
        </div>

        <PanelState busy={busy} error={error} empty={!busy && !error && !rows.length} emptyText="ไม่พบสถานีในกองกำกับการนี้" />

        {!busy && !error && !!rows.length && total && (
          <>
            <h6 className="text-info mb-2"><i className="fa-solid fa-gas-pump"></i> สรุปยอดรวม (น้ำมันเชื้อเพลิง)</h6>
            <div className="row g-3 mb-4">
              <div className="col-md-3 col-6">{kpi('ใช้ไปแล้ว (ลิตร)', num(total.usedL), 'text-danger')}</div>
              <div className="col-md-3 col-6">{kpi('โควตาเชื้อเพลิง (บาท)', num(total.quotaB), 'text-info')}</div>
              <div className="col-md-3 col-6">{kpi('ใช้ไปแล้ว (บาท)', num(total.usedB), 'text-danger')}</div>
              <div className="col-md-3 col-6">{kpi('คงเหลือ (บาท)', num(total.quotaB - total.usedB), remainClass(total.quotaB - total.usedB))}</div>
            </div>

            <h6 className="text-primary mb-2"><i className="fa-solid fa-oil-can"></i> สรุปยอดรวม (น้ำมันเครื่อง)</h6>
            <div className="row g-3 mb-4">
              <div className="col-md-4 col-12">{kpi('โควตาน้ำมันเครื่อง (ลิตร)', num(total.oilQuotaL), 'text-primary')}</div>
              <div className="col-md-4 col-12">{kpi('ใช้ไปแล้ว (ลิตร)', num(total.oilUsedL), 'text-danger')}</div>
              <div className="col-md-4 col-12">{kpi('คงเหลือ (ลิตร)', num(total.oilQuotaL - total.oilUsedL), remainClass(total.oilQuotaL - total.oilUsedL))}</div>
            </div>

            <h6 className="text-white mb-3"><i className="fa-solid fa-chart-column"></i> สรุปการใช้น้ำมันแยกตามสถานี</h6>
            <div className="table-responsive">
              <table className="table table-hq table-bordered text-center align-middle small mb-0">
                <thead>
                  <tr>
                    <th rowSpan={2} className="align-middle text-start">สถานี</th>
                    <th rowSpan={2} className="align-middle text-info">ใช้เชื้อเพลิง (ลิตร)</th>
                    <th colSpan={3} className="text-warning">เชื้อเพลิง (บาท)</th>
                    <th colSpan={3} className="text-primary">น้ำมันเครื่อง (ลิตร)</th>
                    <th rowSpan={2} className="align-middle" style={{ minWidth: 130 }}>สัดส่วนที่ใช้</th>
                  </tr>
                  <tr>
                    <th className="text-warning">โควตา</th><th className="text-danger">ใช้ไป</th><th className="text-success">คงเหลือ</th>
                    <th className="text-primary">โควตา</th><th className="text-danger">ใช้ไป</th><th className="text-success">คงเหลือ</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([id, r]) => (
                    <tr key={id}>
                      <td className="text-start text-white">{r.name}</td>
                      <td>{num(r.usedL)}</td>
                      <td>{num(r.quotaB)}</td>
                      <td className={r.usedB > r.quotaB && r.quotaB > 0 ? 'text-danger fw-bold' : ''}>{num(r.usedB)}</td>
                      <td className={remainClass(r.quotaB - r.usedB)}>{num(r.quotaB - r.usedB)}</td>
                      <td>{num(r.oilQuotaL)}</td>
                      <td className={r.oilUsedL > r.oilQuotaL && r.oilQuotaL > 0 ? 'text-danger fw-bold' : ''}>{num(r.oilUsedL)}</td>
                      <td className={remainClass(r.oilQuotaL - r.oilUsedL)}>{num(r.oilQuotaL - r.oilUsedL)}</td>
                      <td>
                        <div className="progress" style={{ height: 8, background: 'rgba(255,255,255,0.08)' }}>
                          <div className={`progress-bar ${barClass(r.usedB, r.quotaB)}`} style={{ width: `${pct(r.usedB, r.quotaB)}%` }} />
                        </div>
                        <small className="text-white-50">{r.quotaB > 0 ? `${Math.round((r.usedB / r.quotaB) * 100)}%` : 'ยังไม่ตั้งโควตา'}</small>
                      </td>
                    </tr>
                  ))}
                  <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <td className="text-start text-warning fw-bold">{total.name}</td>
                    <td className="fw-bold">{num(total.usedL)}</td>
                    <td className="fw-bold">{num(total.quotaB)}</td>
                    <td className="fw-bold text-danger">{num(total.usedB)}</td>
                    <td className={`fw-bold ${remainClass(total.quotaB - total.usedB)}`}>{num(total.quotaB - total.usedB)}</td>
                    <td className="fw-bold">{num(total.oilQuotaL)}</td>
                    <td className="fw-bold text-danger">{num(total.oilUsedL)}</td>
                    <td className={`fw-bold ${remainClass(total.oilQuotaL - total.oilUsedL)}`}>{num(total.oilQuotaL - total.oilUsedL)}</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="glass-card">
        <h5 className="text-white mb-3"><i className="fa-solid fa-clock-rotate-left text-info"></i> ประวัติการทำรายการในเดือนนี้ ({logs.length} รายการ)</h5>
        {logs.length ? (
          <div className="table-responsive" style={{ maxHeight: 400, overflowY: 'auto' }}>
            <table className="table table-hq table-bordered align-middle small mb-0">
              <thead>
                <tr>
                  <th>วัน/เวลา</th><th className="text-start">สถานี (หน่วย)</th><th className="text-start">ผู้ดำเนินการ</th>
                  <th>รถยนต์</th><th>รายการ</th><th>เลขไมล์</th><th>ระยะทาง</th><th>จำนวนลิตร</th><th>จำนวนเงิน</th><th>ใบเสร็จ</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l, i) => (
                  <tr key={i}>
                    <td className="text-nowrap">{l.date}</td>
                    <td className="text-start">{l.station}<div className="text-white-50" style={{ fontSize: '.72rem' }}>{l.unit}</div></td>
                    <td className="text-start">{l.person}</td>
                    <td>{l.car}</td>
                    <td className={l.type === 'เติมน้ำมัน' ? 'text-info' : 'text-warning'}>{l.type}</td>
                    <td>{l.currentMileage}</td>
                    <td>{l.distance}</td>
                    <td>{num(l.liters)}</td>
                    <td>{l.type === 'เติมน้ำมัน' ? num(l.baht) : '-'}</td>
                    <td>{l.receipt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-white-50 small mb-0">ยังไม่มีรายการเบิกน้ำมันในเดือนที่เลือก</p>
        )}
      </div>

      {quotaOpen && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setQuotaOpen(false)}>
          <div className="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-white">
                  <i className="fa-solid fa-sliders text-warning"></i> ตั้งค่าโควตาประจำเดือน {month}
                </h6>
                <button className="btn-close btn-close-white" onClick={() => setQuotaOpen(false)}></button>
              </div>
              <div className="modal-body">
                <p className="text-white-50 small">กรอกเฉพาะสถานีที่ต้องการเปลี่ยน ช่องที่เว้นว่างจะถูกบันทึกเป็น 0</p>
                <table className="table table-sm table-dark table-borderless align-middle mb-0" style={{ background: 'transparent' }}>
                  <thead>
                    <tr className="text-white-50 small">
                      <th>สถานี</th><th style={{ width: 170 }}>โควตาเชื้อเพลิง (บาท)</th><th style={{ width: 170 }}>โควตาน้ำมันเครื่อง (ล.)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(([id, r]) => (
                      <tr key={id}>
                        <td className="text-white">{r.name}</td>
                        <td>
                          <input type="number" className="form-control form-control-sm bg-dark text-white border-secondary text-end"
                                 value={draft[id]?.baht ?? ''}
                                 onChange={(e) => setDraft({ ...draft, [id]: { ...draft[id], baht: e.target.value } })} />
                        </td>
                        <td>
                          <input type="number" className="form-control form-control-sm bg-dark text-white border-secondary text-end"
                                 value={draft[id]?.oilLiters ?? ''}
                                 onChange={(e) => setDraft({ ...draft, [id]: { ...draft[id], oilLiters: e.target.value } })} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary btn-sm" onClick={() => setQuotaOpen(false)}>ยกเลิก</button>
                <button className="btn btn-warning btn-sm fw-bold" onClick={saveQuota} disabled={saving}>
                  <i className="fa-solid fa-floppy-disk"></i> {saving ? 'กำลังบันทึก...' : 'บันทึกโควตา'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
