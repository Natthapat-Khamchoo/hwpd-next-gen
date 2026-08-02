import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { PanelState, currentMonth, num } from './panelHelpers';

/**
 * ระบบควบคุมโควตาน้ำมัน/น้ำมันเครื่อง (พอร์ตจาก loadHqView('fuel'))
 *
 * ฝอ. ตั้งโควตาเป็นรายเดือนต่อสถานี แล้วระบบเทียบกับยอดเบิกจริงจาก tb_FuelOil
 * แถบใช้ไปเกินโควตาเปลี่ยนเป็นแดง เพราะนั่นคือสิ่งเดียวที่ต้องรีบเห็นในหน้านี้
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
  quota > 0 && used > quota ? 'bg-danger' : used / (quota || 1) > 0.8 ? 'bg-warning' : 'bg-info';

export const FuelPanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState<Record<string, Row> | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [draft, setDraft] = useState<Record<string, { baht: string; oilLiters: string }>>({});
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqFuel(station, month, user?.token);
    if (res.status === 'success') {
      setSummary(res.data.summary);
      setLogs(res.data.logs || []);
      // เติมช่องกรอกด้วยค่าที่บันทึกไว้แล้ว ฝอ. จะได้แก้เฉพาะสถานีที่เปลี่ยน
      const next: Record<string, { baht: string; oilLiters: string }> = {};
      Object.entries(res.data.summary as Record<string, Row>).forEach(([id, row]) => {
        if (id !== 'total') next[id] = { baht: String(row.quotaB || ''), oilLiters: String(row.oilQuotaL || '') };
      });
      setDraft(next);
    } else {
      setError(res.message || 'โหลดข้อมูลน้ำมันไม่สำเร็จ');
    }
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station, month]);

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
      await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const rows = Object.entries(summary || {}).filter(([id]) => id !== 'total');
  const total = summary?.total;

  return (
    <>
      <div className="glass-card mb-4">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <h5 className="text-white m-0"><i className="fa-solid fa-gas-pump text-warning"></i> โควตาและยอดใช้น้ำมัน</h5>
          <input type="month" className="form-control form-control-sm bg-dark text-white border-warning"
                 style={{ width: 180 }} value={month} onChange={(e) => setMonth(e.target.value)} />
        </div>

        <PanelState busy={busy} error={error} empty={!busy && !error && !rows.length} emptyText="ไม่พบสถานีในกองกำกับการนี้" />

        {!busy && !error && !!rows.length && (
          <>
            {total && (
              <div className="row g-3 mb-3">
                {[
                  { l: 'โควตาน้ำมันทั้ง กก. (บาท)', v: num(total.quotaB), c: 'text-info' },
                  { l: 'ใช้ไปแล้ว (บาท)', v: num(total.usedB), c: total.usedB > total.quotaB ? 'text-danger' : 'text-warning' },
                  { l: 'โควตาน้ำมันเครื่อง (ลิตร)', v: num(total.oilQuotaL), c: 'text-info' },
                  { l: 'น้ำมันเครื่องใช้ไป (ลิตร)', v: num(total.oilUsedL), c: total.oilUsedL > total.oilQuotaL ? 'text-danger' : 'text-warning' },
                ].map((k, i) => (
                  <div className="col-md-3 col-6" key={i}>
                    <div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}>
                      <div className="title">{k.l}</div>
                      <div className={`value ${k.c}`}>{k.v}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="table-responsive">
              <table className="table table-hq table-bordered align-middle small mb-0">
                <thead>
                  <tr>
                    <th className="text-start">หน่วย</th>
                    <th style={{ minWidth: 130 }}>โควตา (บาท)</th>
                    <th style={{ minWidth: 130 }}>โควตาน้ำมันเครื่อง (ล.)</th>
                    <th>ใช้ไป (บาท)</th>
                    <th>น้ำมันเครื่อง (ล.)</th>
                    <th style={{ minWidth: 150 }}>สัดส่วนที่ใช้</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([id, row]) => (
                    <tr key={id}>
                      <td className="text-start text-white">{row.name}</td>
                      <td>
                        {canEdit ? (
                          <input type="number" className="form-control form-control-sm bg-dark text-white border-secondary text-end"
                                 value={draft[id]?.baht ?? ''} onChange={(e) => setDraft({ ...draft, [id]: { ...draft[id], baht: e.target.value } })} />
                        ) : num(row.quotaB)}
                      </td>
                      <td>
                        {canEdit ? (
                          <input type="number" className="form-control form-control-sm bg-dark text-white border-secondary text-end"
                                 value={draft[id]?.oilLiters ?? ''} onChange={(e) => setDraft({ ...draft, [id]: { ...draft[id], oilLiters: e.target.value } })} />
                        ) : num(row.oilQuotaL)}
                      </td>
                      <td className={row.usedB > row.quotaB && row.quotaB > 0 ? 'text-danger fw-bold' : ''}>{num(row.usedB)}</td>
                      <td className={row.oilUsedL > row.oilQuotaL && row.oilQuotaL > 0 ? 'text-danger fw-bold' : ''}>{num(row.oilUsedL)}</td>
                      <td>
                        <div className="progress" style={{ height: 8, background: 'rgba(255,255,255,0.08)' }}>
                          <div className={`progress-bar ${barClass(row.usedB, row.quotaB)}`} style={{ width: `${pct(row.usedB, row.quotaB)}%` }} />
                        </div>
                        <small className="text-white-50">{row.quotaB > 0 ? `${Math.round((row.usedB / row.quotaB) * 100)}%` : 'ยังไม่ตั้งโควตา'}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {canEdit && (
              <div className="d-flex justify-content-end mt-3">
                <button className="btn btn-warning fw-bold" onClick={saveQuota} disabled={saving}>
                  <i className="fa-solid fa-floppy-disk"></i> {saving ? 'กำลังบันทึก...' : `บันทึกโควตาเดือน ${month}`}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="glass-card">
        <h5 className="text-white mb-3"><i className="fa-solid fa-receipt text-info"></i> รายการเบิกน้ำมันเดือนนี้ ({logs.length} รายการ)</h5>
        {logs.length ? (
          <div className="table-responsive" style={{ maxHeight: 420, overflowY: 'auto' }}>
            <table className="table table-hq table-bordered align-middle small mb-0">
              <thead>
                <tr>
                  <th>วันที่</th><th className="text-start">หน่วย</th><th>ประเภท</th><th className="text-start">ผู้ดำเนินการ</th>
                  <th>ทะเบียน</th><th>เลขไมล์</th><th>ลิตร</th><th>บาท</th><th>ใบเสร็จ</th><th>ระยะทาง</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l, i) => (
                  <tr key={i}>
                    <td className="text-nowrap">{l.date}</td>
                    <td className="text-start">{l.station}</td>
                    <td className={l.type === 'เติมน้ำมัน' ? 'text-info' : 'text-warning'}>{l.type}</td>
                    <td className="text-start">{l.person}</td>
                    <td>{l.car}</td>
                    <td>{l.currentMileage}</td>
                    <td>{num(l.liters)}</td>
                    <td>{l.type === 'เติมน้ำมัน' ? num(l.baht) : '-'}</td>
                    <td>{l.receipt}</td>
                    <td>{l.distance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-white-50 small mb-0">ยังไม่มีรายการเบิกน้ำมันในเดือนที่เลือก</p>
        )}
      </div>
    </>
  );
};
