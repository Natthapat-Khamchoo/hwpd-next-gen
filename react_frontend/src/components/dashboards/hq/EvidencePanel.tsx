import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { PanelState, RangePicker, recentStart, today } from './panelHelpers';

/**
 * ตารางจัดหมวดหมู่ของกลาง (พอร์ตจาก loadHqView('evidence'))
 *
 * เจ้าหน้าที่กรอกของกลางมาเป็นข้อความอิสระ ("ยาบ้า 200 เม็ด, มีดปลายแหลม 1 เล่ม")
 * ฝอ. มาแยกเป็นรายการ ชื่อ/จำนวน/หน่วย ทีหลัง ตัวเลขบนกราฟหมวดหมู่ของกลางในหน้า
 * ภาพรวมมาจากตรงนี้ คดีที่ยังไม่จัดหมวดจึงไม่ปรากฏบนกราฟเลย
 */

interface Item { name: string; qty: string; unit: string }
interface Row {
  recordId: string;
  date: string;
  station: string;
  unit: string;
  category: string;
  rawItems: string;
  isCategorized: boolean;
  structuredJson: string;
}

const parseItems = (json: string): Item[] => {
  try {
    const parsed = JSON.parse(json || '[]');
    return Array.isArray(parsed)
      ? parsed.map((i: any) => ({ name: String(i?.name ?? ''), qty: String(i?.qty ?? ''), unit: String(i?.unit ?? '') }))
      : [];
  } catch {
    return [];
  }
};

export const EvidencePanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Row | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqEvidence(station, start, end, user?.token);
    if (res.status === 'success') setRows(res.data || []);
    else setError(res.message || 'โหลดรายการของกลางไม่สำเร็จ');
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

  const open = (row: Row) => {
    setEditing(row);
    const parsed = parseItems(row.structuredJson);
    setItems(parsed.length ? parsed : [{ name: '', qty: '', unit: '' }]);
  };

  const save = async () => {
    if (!editing) return;
    const cleaned = items.filter((i) => i.name.trim());
    setSaving(true);
    const res = await api.hqSaveEvidence({ stationId: station, recordId: editing.recordId, items: cleaned }, user?.token);
    setSaving(false);
    if (res.status === 'success') {
      setEditing(null);
      await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const pending = rows.filter((r) => !r.isCategorized).length;

  return (
    <div className="glass-card">
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-1">
        <h5 className="text-white m-0"><i className="fa-solid fa-boxes-packing text-warning"></i> จัดหมวดหมู่ของกลาง</h5>
        {!busy && !!rows.length && (
          <span className={`badge ${pending ? 'bg-warning text-dark' : 'bg-success'}`}>
            {pending ? `รอจัดหมวดหมู่ ${pending} คดี` : 'จัดหมวดหมู่ครบทุกคดีแล้ว'}
          </span>
        )}
      </div>
      <p className="text-white-50 small mb-3">คดีที่ยังไม่จัดหมวดหมู่จะไม่ถูกนับในกราฟของกลางหน้าภาพรวม</p>

      <RangePicker start={start} end={end} onStart={setStart} onEnd={setEnd} onLoad={load} busy={busy} />
      <PanelState busy={busy} error={error} empty={!busy && !error && !rows.length} emptyText="ไม่พบคดีจับกุมในช่วงวันที่ที่เลือก" />

      {!busy && !error && !!rows.length && (
        <div className="table-responsive" style={{ maxHeight: 520, overflowY: 'auto' }}>
          <table className="table table-hq table-bordered align-middle small mb-0">
            <thead>
              <tr>
                <th>วันที่</th><th className="text-start">หน่วย</th><th className="text-start">หัวข้อการจับกุม</th>
                <th className="text-start">ของกลางที่กรอกมา</th><th>สถานะ</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.recordId}>
                  <td className="text-nowrap">{r.date}</td>
                  <td className="text-start">{r.station}<div className="text-white-50" style={{ fontSize: '.72rem' }}>{r.unit}</div></td>
                  <td className="text-start text-white">{r.category}</td>
                  <td className="text-start text-white-50" style={{ maxWidth: 320, whiteSpace: 'pre-wrap' }}>{r.rawItems || '-'}</td>
                  <td>
                    {r.isCategorized
                      ? <span className="badge bg-success">จัดแล้ว</span>
                      : <span className="badge bg-warning text-dark">รอจัด</span>}
                  </td>
                  <td>
                    <button className="btn btn-sm btn-outline-warning py-0 px-2" onClick={() => open(r)}>
                      {canEdit ? 'จัดหมวดหมู่' : 'ดู'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setEditing(null)}>
          <div className="modal-dialog modal-lg modal-dialog-centered" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-white">จัดหมวดหมู่ของกลาง — {editing.category}</h6>
                <button className="btn-close btn-close-white" onClick={() => setEditing(null)}></button>
              </div>
              <div className="modal-body">
                <div className="py-2 px-3 mb-3 small rounded"
                     style={{ whiteSpace: 'pre-wrap', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#cbd5e1' }}>
                  <strong className="text-white">ที่เจ้าหน้าที่กรอกมา:</strong><br />{editing.rawItems || '(ไม่ได้ระบุ)'}
                </div>
                <table className="table table-sm table-dark table-borderless align-middle mb-2" style={{ background: 'transparent' }}>
                  <thead><tr className="text-white-50 small"><th>ชื่อของกลาง</th><th style={{ width: 110 }}>จำนวน</th><th style={{ width: 110 }}>หน่วย</th><th style={{ width: 44 }}></th></tr></thead>
                  <tbody>
                    {items.map((it, i) => (
                      <tr key={i}>
                        <td><input className="form-control form-control-sm bg-dark text-white border-secondary" value={it.name}
                                   disabled={!canEdit}
                                   onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} /></td>
                        <td><input className="form-control form-control-sm bg-dark text-white border-secondary" value={it.qty}
                                   disabled={!canEdit}
                                   onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, qty: e.target.value } : x)))} /></td>
                        <td><input className="form-control form-control-sm bg-dark text-white border-secondary" value={it.unit}
                                   disabled={!canEdit}
                                   onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, unit: e.target.value } : x)))} /></td>
                        <td>{canEdit && items.length > 1 && (
                          <button className="btn btn-sm btn-outline-danger py-0 px-2" onClick={() => setItems(items.filter((_, j) => j !== i))}>
                            <i className="fa-solid fa-xmark"></i>
                          </button>
                        )}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {canEdit && (
                  <button className="btn btn-sm btn-outline-info" onClick={() => setItems([...items, { name: '', qty: '', unit: '' }])}>
                    <i className="fa-solid fa-plus"></i> เพิ่มรายการ
                  </button>
                )}
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary btn-sm" onClick={() => setEditing(null)}>ปิด</button>
                {canEdit && (
                  <button className="btn btn-warning btn-sm fw-bold" onClick={save} disabled={saving}>
                    {saving ? 'กำลังบันทึก...' : 'บันทึก'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
