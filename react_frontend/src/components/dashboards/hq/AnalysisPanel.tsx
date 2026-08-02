import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { downloadSheet } from './excel';
import { PanelState } from './panelHelpers';

/**
 * ตารางแจกแจงเชิงลึก "ข้อหา/หมวดจับกุม x สถานี" (พอร์ตจาก executeHqAnalysis)
 *
 * เป็นเครื่องมือหลักของหน้าภาพรวม ฝอ. ใช้ตอบคำถามว่า "ยอด ว.20 ทั้งกอง 29 ใบ
 * มาจากข้อหาอะไรบ้าง สถานีไหนออกเยอะสุด" ซึ่งดูจากตารางยอดรวมรายสถานีไม่ได้เลย
 *
 * ตัวเลขทุกช่องกดได้ เพราะสิ่งที่ตามมาเสมอคือ "แล้วใบไหนบ้าง" — ของเดิมเก็บ recordId
 * ของแถวที่นับไว้ในแต่ละช่องเพื่อการนี้โดยเฉพาะ
 */

interface Cell { count: number; ids: string[] }
type Breakdown = Record<string, Record<string, Cell>>;

interface Props {
  station: string;
  start: string;
  end: string;
  /** รายสถานีของกองนี้ ใช้เป็นหัวคอลัมน์ ส่งมาจากผลสรุปที่โหลดไว้แล้ว */
  stations: { station: string; name: string }[];
}

export const AnalysisPanel: React.FC<Props> = ({ station, start, end, stations }) => {
  const { user } = useAuth();
  const [mode, setMode] = useState<'daily_charges' | 'arrests'>('daily_charges');
  const [chargeNames, setChargeNames] = useState<string[]>([]);
  const [arrestCats, setArrestCats] = useState<{ name: string; checked: boolean }[]>([]);
  const [picked, setPicked] = useState<Record<string, Set<string>>>({ daily_charges: new Set(), arrests: new Set() });
  const [data, setData] = useState<Breakdown | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [drill, setDrill] = useState<{ label: string; rows: any[] } | null>(null);

  useEffect(() => {
    // ข้อหาโหลดจากตารางอ้างอิงเดียวกับที่ฟอร์มใช้ จะได้ไม่ต้องมาไล่แก้สองที่เวลาเพิ่มข้อหา
    api.getChargeDropdown(user?.token).then((list) => {
      const names = (list || []).filter(Boolean);
      setChargeNames(names);
      setPicked((p) => ({ ...p, daily_charges: new Set(names) }));
    });
    api.hqAnalysisCategories(user?.token).then((res) => {
      if (res.status !== 'success') return;
      setArrestCats(res.data);
      setPicked((p) => ({ ...p, arrests: new Set(res.data.filter((c: any) => c.checked).map((c: any) => c.name)) }));
    });
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  const options = mode === 'daily_charges' ? chargeNames : arrestCats.map((c) => c.name);
  const selected = picked[mode];

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setPicked({ ...picked, [mode]: next });
  };

  const toggleAll = () => {
    const next = selected.size === options.length ? new Set<string>() : new Set(options);
    setPicked({ ...picked, [mode]: next });
  };

  const run = async () => {
    if (!selected.size) return setError('กรุณาเลือกอย่างน้อยหนึ่งรายการ');
    setError('');
    setBusy(true);
    setData(null);
    const res = await api.hqAnalysis(
      { stationId: station, start, end, mode, categories: Array.from(selected) },
      user?.token,
    );
    setBusy(false);
    if (res.status !== 'success') return setError(res.message || 'ประมวลผลไม่สำเร็จ');
    setData(res.data);
  };

  const openCell = async (category: string, cell: Cell, where: string) => {
    if (!cell.ids.length) return;
    const table = mode === 'daily_charges' ? 'tb_DailyResult' : 'tb_Arrests';
    setDrill({ label: `${category} — ${where}`, rows: [] });
    const res = await api.hqRecords({ stationId: station, sheetName: table, recordIds: cell.ids }, user?.token);
    setDrill({ label: `${category} — ${where}`, rows: res.status === 'success' ? res.data : [] });
  };

  // เรียงจากมากไปน้อย เพราะสิ่งที่ต้องเห็นก่อนคือข้อหาที่ออกเยอะที่สุด
  const rows = useMemo(
    () =>
      Object.entries(data || {})
        .map(([category, cells]) => ({ category, cells }))
        .sort((a, b) => (b.cells.total?.count || 0) - (a.cells.total?.count || 0)),
    [data],
  );

  const exportExcel = () => {
    const header = ['รายการ', ...stations.map((s) => s.name), 'รวม'];
    const body = rows.map((r) => [
      r.category,
      ...stations.map((s) => r.cells[s.station]?.count ?? 0),
      r.cells.total?.count ?? 0,
    ]);
    const title = mode === 'daily_charges' ? 'แจกแจงข้อหา ว.20' : 'แจกแจงหมวดรายงานจับกุม';
    downloadSheet(`${title}_${start}_${end}`, [[title], [`ช่วงวันที่ ${start} ถึง ${end}`], [], header, ...body]);
  };

  return (
    <div className="glass-card mb-4">
      <h5 className="text-white mb-3"><i className="fa-solid fa-filter text-info"></i> แจกแจงรายละเอียดข้อหา / คดีแยกตามสถานี</h5>

      <div className="btn-group w-100 mb-3" role="group">
        <button className={`btn py-2 ${mode === 'daily_charges' ? 'btn-info' : 'btn-outline-info'}`}
                onClick={() => { setMode('daily_charges'); setData(null); }}>
          <i className="fa-solid fa-file-invoice"></i> 1. ชำแหละ ข้อหา ว.20
        </button>
        <button className={`btn py-2 ${mode === 'arrests' ? 'btn-danger' : 'btn-outline-danger'}`}
                onClick={() => { setMode('arrests'); setData(null); }}>
          <i className="fa-solid fa-handcuffs"></i> 2. ชำแหละ หมวดรายงานจับกุม
        </button>
      </div>

      <div className="d-flex justify-content-between align-items-center mb-2">
        <label className="text-info small fw-bold">คลิกเลือกรายการที่ต้องการชำแหละข้อมูล ({selected.size}/{options.length}):</label>
        <button className="btn btn-sm btn-outline-info fw-bold" onClick={toggleAll}>
          <i className="fa-solid fa-check-double"></i> เลือกทั้งหมด / ยกเลิก
        </button>
      </div>

      <div className="p-3 rounded border border-secondary mb-3"
           style={{ background: 'rgba(0,0,0,0.25)', maxHeight: 220, overflowY: 'auto' }}>
        {options.length ? (
          <div className="row g-2">
            {options.map((name) => (
              <div className="col-md-4 col-6" key={name}>
                <label className="d-flex align-items-center gap-2 text-white small" style={{ cursor: 'pointer' }}>
                  <input type="checkbox" checked={selected.has(name)} onChange={() => toggle(name)} />
                  <span className="text-truncate" title={name}>{name}</span>
                </label>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-white-50 small">กำลังโหลดรายการ...</div>
        )}
      </div>

      <div className="d-flex justify-content-between align-items-center mb-3">
        <button className="btn btn-info fw-bold" onClick={run} disabled={busy}>
          <i className="fa-solid fa-chart-pie"></i> {busy ? 'กำลังประมวลผล...' : 'ประมวลผล'}
        </button>
        {!!rows.length && (
          <button className="btn btn-sm btn-success fw-bold px-3" onClick={exportExcel}>
            <i className="fa-solid fa-file-excel"></i> ส่งออก Excel
          </button>
        )}
      </div>

      <PanelState busy={busy} error={error} empty={false} emptyText="" />

      {!busy && !!rows.length && (
        <>
          <p className="text-white-50 small mb-2">
            <i className="fa-solid fa-hand-pointer text-info"></i> คลิกที่ตัวเลขเพื่อดูว่ายอดนั้นมาจากใบงานไหนบ้าง
          </p>
          <div className="table-responsive">
            <table className="table table-hq table-bordered align-middle small mb-0">
              <thead>
                <tr className="text-center">
                  <th className="text-start" style={{ minWidth: 200 }}>
                    {mode === 'daily_charges' ? 'รายการข้อหา' : 'หมวดการจับกุม'}
                  </th>
                  {stations.map((s) => <th key={s.station}>{s.name}</th>)}
                  <th className="text-warning">รวม</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ category, cells }) => (
                  <tr key={category}>
                    <td className="text-start text-white">{category}</td>
                    {stations.map((s) => {
                      const cell = cells[s.station] || { count: 0, ids: [] };
                      return (
                        <td key={s.station} className="text-center">
                          {cell.count ? (
                            <button className="btn btn-link p-0 text-info fw-bold text-decoration-none"
                                    onClick={() => openCell(category, cell, s.name)}>
                              {cell.count}
                            </button>
                          ) : <span className="text-white-50">0</span>}
                        </td>
                      );
                    })}
                    <td className="text-center text-warning fw-bold">
                      {cells.total?.count ? (
                        <button className="btn btn-link p-0 text-warning fw-bold text-decoration-none"
                                onClick={() => openCell(category, cells.total, 'ทั้งกองกำกับการ')}>
                          {cells.total.count}
                        </button>
                      ) : 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!busy && data && !rows.length && (
        <p className="text-white-50 small mb-0">ไม่พบข้อมูลของรายการที่เลือกในช่วงวันที่นี้</p>
      )}

      {drill && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setDrill(null)}>
          <div className="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-white">ใบงานที่เกี่ยวข้อง — {drill.label}</h6>
                <button className="btn-close btn-close-white" onClick={() => setDrill(null)}></button>
              </div>
              <div className="modal-body">
                {!drill.rows.length ? (
                  <div className="text-white-50 small py-3">กำลังโหลด...</div>
                ) : drill.rows.map((r) => (
                  <div key={r.recordId} className="p-3 mb-2 rounded"
                       style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <div className="d-flex justify-content-between align-items-start gap-2 mb-1">
                      <div className="text-white fw-bold">{r.title}</div>
                      <span className={`badge ${r.tagClass}`}>{r.tag}</span>
                    </div>
                    <div className="text-white-50" style={{ fontSize: '.78rem' }}>
                      {r.date} · {r.station} {r.unit}
                    </div>
                    {r.charges && <div className="text-white-50 mt-2" style={{ fontSize: '.8rem' }}><b>ข้อหา:</b> {r.charges}</div>}
                    {r.detail && <div className="text-white-50 mt-1" style={{ fontSize: '.8rem' }}><b>พฤติการณ์:</b> {r.detail}</div>}
                  </div>
                ))}
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary btn-sm" onClick={() => setDrill(null)}>ปิด</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
