import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { downloadSheet } from './excel';
import { PanelState, RangePicker, recentStart, today } from './panelHelpers';

/**
 * ระบบจัดการการนำขบวน (พอร์ตจาก loadHqView('escort'))
 *
 * งานนำขบวนมาจากส่วนกลางสั่งลงมา ไม่ใช่รายงานที่สถานีส่งขึ้น จึงบันทึกเป็นอนุมัติ
 * ทันทีไม่ต้องผ่านคิว ตรงกับที่ saveHQEscort ของเดิมเขียน Approved ลงไปเลย
 */

const ESCORT_TYPES = ['นำขบวนบุคคลสำคัญ (VIP)', 'นำขบวนทั่วไป', 'นำขบวนขนย้ายสิ่งของ'];

interface Row {
  recordId: string;
  type: string;
  station: string;
  start: string;
  end: string;
  details: string;
  fileUrl: string;
  actionBy: string;
}

export const EscortPanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState({ vip: 0, general: 0, total: 0 });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({ escortType: ESCORT_TYPES[0], startDateTime: '', endDateTime: '', details: '' });

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqEscort(station, start, end, user?.token);
    if (res.status === 'success') {
      setRows(res.data.records || []);
      setSummary(res.data.summary || { vip: 0, general: 0, total: 0 });
    } else {
      setError(res.message || 'โหลดข้อมูลการนำขบวนไม่สำเร็จ');
    }
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

  const save = async () => {
    if (!form.startDateTime) return Swal.fire('แจ้งเตือน', 'กรุณาระบุวันเวลาเริ่มนำขบวน', 'warning');
    setSaving(true);
    const res = await api.hqSaveEscort({ stationId: station, ...form }, user?.token);
    setSaving(false);
    if (res.status === 'success') {
      setFormOpen(false);
      setForm({ escortType: ESCORT_TYPES[0], startDateTime: '', endDateTime: '', details: '' });
      await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const exportExcel = () => {
    downloadSheet('นำขบวน_' + start + '_' + end, [
      ['รายการภารกิจนำขบวน ช่วงวันที่ ' + start + ' ถึง ' + end],
      [],
      ['ยอดรวม', summary.total, 'บุคคลสำคัญ', summary.vip, 'ทั่วไป', summary.general],
      [],
      ['สถานีรับผิดชอบ', 'ประเภท', 'วัน-เวลาเริ่ม', 'วัน-เวลาสิ้นสุด', 'รายละเอียดภารกิจ', 'ผู้บันทึก', 'หนังสือสั่งการ'],
      ...rows.map((r) => [r.station, r.type, r.start, r.end, r.details, r.actionBy, r.fileUrl]),
    ], 'นำขบวน');
  };

  return (
    <>
      <div className="glass-card">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 border-bottom border-secondary pb-3 mb-3">
          <h5 className="text-white m-0"><i className="fa-solid fa-motorcycle text-info"></i> ระบบจัดการการนำขบวน (ฝอ.)</h5>
          {canEdit && (
            <button className="btn btn-primary fw-bold px-4" onClick={() => setFormOpen(true)}>
              <i className="fa-solid fa-plus"></i> บันทึกภารกิจนำขบวน
            </button>
          )}
        </div>

        <div className="d-flex flex-wrap align-items-center gap-2">
          <RangePicker start={start} end={end} onStart={setStart} onEnd={setEnd} onLoad={load} busy={busy} />
          <button className="btn btn-success btn-sm fw-bold mb-3" onClick={exportExcel} disabled={!rows.length}>
            <i className="fa-solid fa-file-excel"></i> Export Excel
          </button>
        </div>

        {!busy && !error && (
          <div className="row g-3 mb-3">
            {[
              { l: 'นำขบวนทั้งหมด', v: summary.total, c: 'text-info' },
              { l: 'บุคคลสำคัญ (VIP)', v: summary.vip, c: 'text-warning' },
              { l: 'ทั่วไป', v: summary.general, c: 'text-secondary' },
            ].map((k, i) => (
              <div className="col-md-4 col-12" key={i}>
                <div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <div className="title">{k.l}</div><div className={`value ${k.c}`}>{k.v}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        <PanelState busy={busy} error={error} empty={!busy && !error && !rows.length} emptyText="ไม่มีงานนำขบวนในช่วงวันที่ที่เลือก" />

        {!busy && !error && !!rows.length && (
          <div className="table-responsive">
            <table className="table table-hq table-bordered align-middle small mb-0">
              <thead>
                <tr><th className="text-start">ประเภท</th><th className="text-start">หน่วย</th><th>เริ่ม</th><th>สิ้นสุด</th>
                    <th className="text-start">รายละเอียด</th><th className="text-start">ผู้บันทึก</th><th>ไฟล์</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.recordId}>
                    <td className={`text-start ${r.type.includes('บุคคลสำคัญ') ? 'text-warning' : ''}`}>{r.type}</td>
                    <td className="text-start">{r.station}</td>
                    <td className="text-nowrap">{r.start}</td>
                    <td className="text-nowrap">{r.end}</td>
                    <td className="text-start text-white-50" style={{ maxWidth: 320, whiteSpace: 'pre-wrap' }}>{r.details || '-'}</td>
                    <td className="text-start">{r.actionBy}</td>
                    <td>
                      {r.fileUrl && r.fileUrl.startsWith('http')
                        ? <a href={r.fileUrl} target="_blank" rel="noreferrer" className="text-info"><i className="fa-solid fa-folder-open"></i></a>
                        : <span className="text-white-50">-</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {formOpen && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setFormOpen(false)}>
          <div className="modal-dialog modal-lg modal-dialog-centered" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-white">
                  <i className="fa-solid fa-motorcycle text-info"></i> บันทึกภารกิจนำขบวน
                </h6>
                <button className="btn-close btn-close-white" onClick={() => setFormOpen(false)}></button>
              </div>
              <div className="modal-body">
                <div className="row g-3">
            <div className="col-12 col-md-4">
              <label className="form-label small text-white-50">ประเภทการนำขบวน</label>
              <select className="form-select form-select-sm bg-dark text-white border-secondary"
                      value={form.escortType} onChange={(e) => setForm({ ...form, escortType: e.target.value })}>
                {ESCORT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="col-12 col-md-4">
              <label className="form-label small text-white-50">วันเวลาเริ่ม</label>
              <input type="datetime-local" className="form-control form-control-sm bg-dark text-white border-secondary"
                     value={form.startDateTime} onChange={(e) => setForm({ ...form, startDateTime: e.target.value })} />
            </div>
            <div className="col-12 col-md-4">
              <label className="form-label small text-white-50">วันเวลาสิ้นสุด</label>
              <input type="datetime-local" className="form-control form-control-sm bg-dark text-white border-secondary"
                     value={form.endDateTime} onChange={(e) => setForm({ ...form, endDateTime: e.target.value })} />
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">รายละเอียด (เส้นทาง ผู้ร่วมขบวน หมายเหตุ)</label>
              <textarea className="form-control form-control-sm bg-dark text-white border-secondary" rows={2}
                        value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} />
            </div>
            </div>
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary btn-sm" onClick={() => setFormOpen(false)}>ยกเลิก</button>
                <button className="btn btn-info btn-sm fw-bold" onClick={save} disabled={saving}>
                  <i className="fa-solid fa-floppy-disk"></i> {saving ? 'กำลังบันทึก...' : 'บันทึกงานนำขบวน'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
