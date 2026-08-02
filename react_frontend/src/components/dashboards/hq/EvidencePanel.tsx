import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { downloadSheet } from './excel';
import { EVIDENCE_CATEGORIES, EVIDENCE_MASTER } from './evidenceTypes';
import { PanelState, RangePicker, recentStart, today } from './panelHelpers';

/**
 * ตารางจัดหมวดหมู่ของกลาง (พอร์ตจาก loadHQEvidenceList / renderEvidenceTable)
 *
 * เจ้าหน้าที่กรอกของกลางมาเป็นข้อความอิสระ ("ยาบ้า 200 เม็ด, มีดปลายแหลม 1 เล่ม")
 * ฝอ. มาแยกเป็นรายการ หมวด/ชนิด/จำนวน/หน่วย ทีหลัง กราฟหมวดหมู่ของกลางในหน้า
 * ภาพรวมและรายงานสรุปยอดนับจากตรงนี้ คดีที่ยังไม่จัดจึงไม่ปรากฏบนกราฟเลย
 *
 * หมวดกับชนิดเลือกจากรายการปิดตาย (EVIDENCE_MASTER) ตามของเดิม ไม่ให้พิมพ์เอง
 * เพราะการนับยอดต้องอาศัยข้อความที่ตรงกันเป๊ะ
 */

interface Item { cat: string; type: string; qty: string; unit: string }
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
    if (!Array.isArray(parsed)) return [];
    return parsed.map((i: any) => ({
      // แถวที่บันทึกไว้ก่อนหน้านี้ใช้คีย์ name ยังอ่านขึ้นมาแก้ต่อได้
      cat: String(i?.cat ?? ''),
      type: String(i?.type ?? i?.name ?? ''),
      qty: String(i?.qty ?? ''),
      unit: String(i?.unit ?? ''),
    }));
  } catch {
    return [];
  }
};

const blankItem = (): Item => ({ cat: '', type: '', qty: '', unit: '' });

export const EvidencePanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  // ค่าเริ่มต้นคือ "รอจัดหมวดหมู่" ตามของเดิม เพราะหน้านี้เปิดมาเพื่อเคลียร์งานค้าง
  const [filter, setFilter] = useState<'all' | 'pending' | 'done'>('pending');
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

  const shown = rows.filter((r) =>
    filter === 'all' ? true : filter === 'pending' ? !r.isCategorized : r.isCategorized,
  );
  const pending = rows.filter((r) => !r.isCategorized).length;

  const open = (row: Row) => {
    setEditing(row);
    const parsed = parseItems(row.structuredJson);
    setItems(parsed.length ? parsed : [blankItem()]);
  };

  const setItem = (index: number, patch: Partial<Item>) =>
    setItems(items.map((it, i) => (i === index ? { ...it, ...patch } : it)));

  const pickCategory = (index: number, cat: string) =>
    // เปลี่ยนหมวดแล้วชนิดเดิมใช้ไม่ได้ ต้องล้าง และเติมหน่วยตั้งต้นของหมวดใหม่ให้
    setItem(index, { cat, type: '', unit: cat ? EVIDENCE_MASTER[cat].defaultUnit : '' });

  const save = async (asEmpty = false) => {
    if (!editing) return;
    const cleaned = asEmpty ? [] : items.filter((i) => i.cat && i.type);
    if (!asEmpty && !cleaned.length) {
      return Swal.fire('ข้อมูลไม่ครบ', 'เลือกหมวดและชนิดของกลางอย่างน้อยหนึ่งรายการ', 'warning');
    }
    setSaving(true);
    const res = await api.hqSaveEvidence({ stationId: station, recordId: editing.recordId, items: cleaned }, user?.token);
    setSaving(false);
    if (res.status === 'success') {
      setEditing(null);
      await Swal.fire('บันทึกแล้ว', asEmpty ? 'บันทึกว่าคดีนี้ไม่มีของกลาง' : res.message || '', 'success');
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const markNoEvidence = async () => {
    const confirm = await Swal.fire({
      title: 'ยืนยัน',
      text: 'บันทึกว่าคดีนี้ไม่มีของกลาง? คดีจะถูกนับเป็นจัดหมวดหมู่แล้ว',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'ยืนยัน',
      cancelButtonText: 'ยกเลิก',
    });
    if (confirm.isConfirmed) save(true);
  };

  /** รวมยอดของกลางทุกคดีที่จัดหมวดหมู่แล้ว แยกตาม หมวด+ชนิด+หน่วย */
  const summary = useMemo(() => {
    const map = new Map<string, { cat: string; type: string; unit: string; qty: number; cases: number }>();
    rows.filter((r) => r.isCategorized).forEach((r) => {
      parseItems(r.structuredJson).forEach((it) => {
        if (!it.cat && !it.type) return;
        const key = `${it.cat}|||${it.type}|||${it.unit}`;
        const bucket = map.get(key) || { cat: it.cat, type: it.type, unit: it.unit, qty: 0, cases: 0 };
        bucket.qty += parseFloat(it.qty) || 0;
        bucket.cases += 1;
        map.set(key, bucket);
      });
    });
    return Array.from(map.values()).sort((a, b) =>
      a.cat === b.cat ? a.type.localeCompare(b.type, 'th') : a.cat.localeCompare(b.cat, 'th'),
    );
  }, [rows]);

  const showSummary = () => {
    if (!summary.length) {
      return Swal.fire('แจ้งเตือน', 'ไม่พบของกลางที่ถูกจัดหมวดหมู่แล้วในช่วงวันที่ที่ค้นหา', 'info');
    }
    const body = summary
      .map((s) => `<tr><td style="text-align:left">${s.cat}</td><td style="text-align:left">${s.type}</td>` +
                  `<td style="text-align:right">${s.qty.toLocaleString('th-TH')}</td><td>${s.unit}</td><td>${s.cases}</td></tr>`)
      .join('');
    Swal.fire({
      title: 'สรุปยอดของกลาง',
      width: 720,
      html: `<table style="width:100%;font-size:.85rem;border-collapse:collapse">
        <thead><tr style="border-bottom:1px solid #666">
          <th style="text-align:left">หมวด</th><th style="text-align:left">ชนิด</th>
          <th style="text-align:right">จำนวน</th><th>หน่วย</th><th>คดี</th>
        </tr></thead><tbody>${body}</tbody></table>`,
      confirmButtonText: 'ปิด',
    });
  };

  const exportList = () => {
    downloadSheet(`ของกลาง_${start}_${end}`, [
      [`รายการของกลาง ช่วงวันที่ ${start} ถึง ${end}`],
      [],
      ['วัน/เวลา', 'สถานี', 'หน่วย', 'ข้อหาหลัก', 'ของกลางที่บันทึก (ต้นฉบับ)', 'สถานะ', 'หมวด/ชนิดที่จัดแล้ว'],
      ...shown.map((r) => [
        r.date, r.station, r.unit, r.category, r.rawItems,
        r.isCategorized ? 'จัดหมวดหมู่แล้ว' : 'รอจัดหมวดหมู่',
        parseItems(r.structuredJson).map((i) => `${i.cat}/${i.type} ${i.qty} ${i.unit}`).join(', '),
      ]),
    ], 'รายการของกลาง');
  };

  const exportSummary = () => {
    if (!summary.length) return Swal.fire('แจ้งเตือน', 'ยังไม่มีของกลางที่จัดหมวดหมู่แล้ว', 'info');
    downloadSheet(`สรุปยอดของกลาง_${start}_${end}`, [
      [`สรุปยอดของกลาง ช่วงวันที่ ${start} ถึง ${end}`],
      [],
      ['หมวด', 'ชนิด', 'จำนวนรวม', 'หน่วย', 'จำนวนคดี'],
      ...summary.map((s) => [s.cat, s.type, s.qty, s.unit, s.cases]),
    ], 'สรุปยอด');
  };

  return (
    <div className="glass-card">
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-1">
        <h5 className="text-warning m-0"><i className="fa-solid fa-boxes-packing"></i> ตารางจัดหมวดหมู่ของกลางเข้าคลังข้อมูล (ฝอ.)</h5>
        {!busy && !!rows.length && (
          <span className={`badge ${pending ? 'bg-warning text-dark' : 'bg-success'}`}>
            {pending ? `รอจัดหมวดหมู่ ${pending} คดี` : 'จัดหมวดหมู่ครบทุกคดีแล้ว'}
          </span>
        )}
      </div>
      <p className="text-white-50 small mb-3">คดีที่ยังไม่จัดหมวดหมู่จะไม่ถูกนับในกราฟของกลางหน้าภาพรวม</p>

      <div className="p-3 rounded border border-secondary mb-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
        <RangePicker start={start} end={end} onStart={setStart} onEnd={setEnd} onLoad={load} busy={busy} />
        <div className="d-flex flex-wrap gap-2">
          <select className="form-select form-select-sm bg-dark text-white border-secondary" style={{ width: 190 }}
                  value={filter} onChange={(e) => setFilter(e.target.value as any)}>
            <option value="all">ดูทั้งหมด</option>
            <option value="pending">รอจัดหมวดหมู่</option>
            <option value="done">จัดหมวดหมู่แล้ว</option>
          </select>
          <button className="btn btn-sm btn-warning text-dark fw-bold" onClick={showSummary}>
            <i className="fa-solid fa-chart-pie"></i> สรุปยอด
          </button>
          <button className="btn btn-sm btn-success fw-bold" onClick={exportList} disabled={!shown.length}>
            <i className="fa-solid fa-file-excel"></i> Export รายการ
          </button>
          <button className="btn btn-sm btn-outline-success fw-bold" onClick={exportSummary} disabled={!summary.length}>
            <i className="fa-solid fa-file-excel"></i> Export สรุปยอด
          </button>
          <span className="text-white-50 small align-self-center">แสดง {shown.length} จาก {rows.length} คดี</span>
        </div>
      </div>

      <PanelState busy={busy} error={error} empty={!busy && !error && !shown.length}
                  emptyText={rows.length ? 'ไม่มีคดีที่ตรงกับตัวกรอง' : 'ไม่พบคดีจับกุมในช่วงวันที่ที่เลือก'} />

      {!busy && !error && !!shown.length && (
        <div className="table-responsive" style={{ maxHeight: 520, overflowY: 'auto' }}>
          <table className="table table-hq table-bordered align-middle small mb-0">
            <thead>
              <tr>
                <th>วัน/เวลา (สถานี)</th><th className="text-start">ข้อหาหลัก</th>
                <th className="text-start">ของกลางที่บันทึก (ข้อความต้นฉบับ)</th><th>สถานะ</th><th>จัดการ</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.recordId}>
                  <td className="text-nowrap">{r.date}<div className="text-white-50" style={{ fontSize: '.72rem' }}>{r.station} · {r.unit}</div></td>
                  <td className="text-start text-white">{r.category}</td>
                  <td className="text-start text-white-50" style={{ maxWidth: 340, whiteSpace: 'pre-wrap' }}>{r.rawItems || '-'}</td>
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
          <div className="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable" onClick={(e) => e.stopPropagation()}>
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
                  <thead>
                    <tr className="text-white-50 small">
                      <th style={{ minWidth: 180 }}>หมวดของกลาง</th><th style={{ minWidth: 180 }}>ชนิด</th>
                      <th style={{ width: 110 }}>จำนวน</th><th style={{ width: 120 }}>หน่วย</th><th style={{ width: 44 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it, i) => (
                      <tr key={i}>
                        <td>
                          <select className="form-select form-select-sm bg-dark text-white border-secondary"
                                  value={it.cat} disabled={!canEdit} onChange={(e) => pickCategory(i, e.target.value)}>
                            <option value="">-- เลือกหมวด --</option>
                            {EVIDENCE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </td>
                        <td>
                          <select className="form-select form-select-sm bg-dark text-white border-secondary"
                                  value={it.type} disabled={!canEdit || !it.cat} onChange={(e) => setItem(i, { type: e.target.value })}>
                            <option value="">-- เลือกชนิด --</option>
                            {(EVIDENCE_MASTER[it.cat]?.types || []).map((t) => <option key={t} value={t}>{t}</option>)}
                          </select>
                        </td>
                        <td>
                          <input type="number" step="any" className="form-control form-control-sm bg-dark text-white border-secondary text-end"
                                 value={it.qty} disabled={!canEdit} onChange={(e) => setItem(i, { qty: e.target.value })} />
                        </td>
                        <td>
                          <input className="form-control form-control-sm bg-dark text-white border-secondary"
                                 value={it.unit} disabled={!canEdit} onChange={(e) => setItem(i, { unit: e.target.value })} />
                        </td>
                        <td>
                          {canEdit && items.length > 1 && (
                            <button className="btn btn-sm btn-outline-danger py-0 px-2" onClick={() => setItems(items.filter((_, j) => j !== i))}>
                              <i className="fa-solid fa-xmark"></i>
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {canEdit && (
                  <button className="btn btn-sm btn-outline-info" onClick={() => setItems([...items, blankItem()])}>
                    <i className="fa-solid fa-plus"></i> เพิ่มรายการ
                  </button>
                )}
              </div>
              <div className="modal-footer border-secondary">
                {canEdit && (
                  <button className="btn btn-outline-secondary btn-sm me-auto" onClick={markNoEvidence} disabled={saving}>
                    <i className="fa-solid fa-ban"></i> คดีนี้ไม่มีของกลาง
                  </button>
                )}
                <button className="btn btn-secondary btn-sm" onClick={() => setEditing(null)}>ปิด</button>
                {canEdit && (
                  <button className="btn btn-warning btn-sm fw-bold" onClick={() => save()} disabled={saving}>
                    <i className="fa-solid fa-floppy-disk"></i> {saving ? 'กำลังบันทึก...' : 'บันทึก'}
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
