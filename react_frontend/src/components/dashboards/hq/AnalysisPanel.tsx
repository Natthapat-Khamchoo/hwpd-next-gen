import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { downloadSheet } from './excel';
import { ReactApexChart, vBarOptions } from '../chartHelpers';
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
  // requirement ข้อ 6 — กรองสถิติตามฐานความผิด ทั้งรายข้อหาและทั้งกลุ่ม พ.ร.บ.
  const [chargeGroups, setChargeGroups] = useState<{ group: string; charges: string[] }[]>([]);
  const [groupFilter, setGroupFilter] = useState('');
  const [search, setSearch] = useState('');
  const [arrestCats, setArrestCats] = useState<{ name: string; checked: boolean }[]>([]);
  const [picked, setPicked] = useState<Record<string, Set<string>>>({ daily_charges: new Set(), arrests: new Set() });
  const [data, setData] = useState<Breakdown | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [drill, setDrill] = useState<{ label: string; rows: any[] } | null>(null);
  // เปรียบเทียบสองช่วงเวลาของรายการเดียว — ของเดิมเปิดจากปุ่มข้างชื่อข้อหาในตาราง
  const [compare, setCompare] = useState<string>('');
  const [cmpRange, setCmpRange] = useState({ s1: '', e1: '', s2: start, e2: end });
  const [cmpData, setCmpData] = useState<any | null>(null);
  const [cmpBusy, setCmpBusy] = useState(false);

  useEffect(() => {
    // ข้อหาโหลดจากตารางอ้างอิงเดียวกับที่ฟอร์มใช้ จะได้ไม่ต้องมาไล่แก้สองที่เวลาเพิ่มข้อหา
    api.getChargeGroups(user?.token).then((res) => {
      const names = (res.flat || []).filter(Boolean);
      setChargeNames(names);
      setChargeGroups(res.groups || []);
      setPicked((p) => ({ ...p, daily_charges: new Set(names) }));
    });
    api.hqAnalysisCategories(user?.token).then((res) => {
      if (res.status !== 'success') return;
      setArrestCats(res.data);
      setPicked((p) => ({ ...p, arrests: new Set(res.data.filter((c: any) => c.checked).map((c: any) => c.name)) }));
    });
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  const allOptions = mode === 'daily_charges' ? chargeNames : arrestCats.map((c) => c.name);

  // ตัวกรองมีผลกับ "รายการที่เห็น" เท่านั้น ไม่ได้ล้างสิ่งที่ติ๊กไว้แล้ว เพราะการกรอง
  // แล้วลบตัวเลือกทิ้งเงียบ ๆ จะทำให้ผลลัพธ์ไม่ตรงกับที่ผู้ใช้คิดว่าเลือกไว้
  const groupNames = mode === 'daily_charges' && groupFilter
    ? new Set(chargeGroups.find((g) => g.group === groupFilter)?.charges || [])
    : null;
  const options = allOptions.filter(
    (name) => (!groupNames || groupNames.has(name)) && (!search || name.includes(search)),
  );
  const selected = picked[mode];

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setPicked({ ...picked, [mode]: next });
  };

  /** เลือก/ยกเลิกเฉพาะรายการที่มองเห็นอยู่ตอนนี้ ไม่แตะรายการที่ถูกกรองออกไป */
  const toggleAll = () => {
    const next = new Set(selected);
    const allVisiblePicked = options.every((name) => next.has(name));
    options.forEach((name) => (allVisiblePicked ? next.delete(name) : next.add(name)));
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

  const openCompare = (category: string) => {
    // ตั้งช่วงที่ 1 เป็นเดือนก่อนหน้าช่วงที่กำลังดูอยู่ ซึ่งเป็นการเทียบที่ใช้บ่อยที่สุด
    const from = new Date(start);
    const prevEnd = new Date(from.getTime() - 86400000);
    const prevStart = new Date(prevEnd.getTime() - (new Date(end).getTime() - from.getTime()));
    const iso = (d: Date) => d.toISOString().split('T')[0];
    setCmpRange({ s1: iso(prevStart), e1: iso(prevEnd), s2: start, e2: end });
    setCmpData(null);
    setCompare(category);
  };

  const runCompare = async () => {
    const { s1, e1, s2, e2 } = cmpRange;
    if (!s1 || !e1 || !s2 || !e2) return;
    setCmpBusy(true);
    const res = await api.hqComparison(
      {
        stationId: station, mode, category: compare,
        ranges: [{ start: s1, end: e1 }, { start: s2, end: e2 }],
      },
      user?.token,
    );
    setCmpBusy(false);
    setCmpData(res.status === 'success' ? res.data : null);
  };

  /** % เปลี่ยนแปลงของยอดรวมทั้งกอง (ช่องแรกของทุกชุดคือ total) */
  const growth = (() => {
    if (!cmpData) return null;
    const p1 = cmpData.series[0]?.data[0] || 0;
    const p2 = cmpData.series[1]?.data[0] || 0;
    if (!p1 && !p2) return { text: 'ไม่มีข้อมูลในทั้ง 2 ช่วงเวลา', cls: 'text-white-50', icon: 'fa-minus' };
    if (!p1) return { text: `เพิ่มขึ้น 100% (จาก 0 เป็น ${p2})`, cls: 'text-danger', icon: 'fa-arrow-trend-up' };
    const pct = ((p2 - p1) / p1) * 100;
    if (pct > 0) return { text: `เพิ่มขึ้น ${pct.toFixed(1)}%`, cls: 'text-danger', icon: 'fa-arrow-trend-up' };
    if (pct < 0) return { text: `ลดลง ${Math.abs(pct).toFixed(1)}%`, cls: 'text-success', icon: 'fa-arrow-trend-down' };
    return { text: 'คงที่ (0%)', cls: 'text-info', icon: 'fa-minus' };
  })();

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

      {mode === 'daily_charges' && (
        <div className="row g-2 mb-2">
          <div className="col-12 col-md-5">
            <select className="form-select form-select-sm" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}>
              <option value="">— ทุกกลุ่ม พ.ร.บ. —</option>
              {chargeGroups.map((g) => (
                <option key={g.group} value={g.group}>{g.group} ({g.charges.length})</option>
              ))}
            </select>
          </div>
          <div className="col-12 col-md-5">
            <input
              className="form-control form-control-sm"
              placeholder="ค้นหาชื่อข้อหา..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="col-12 col-md-2">
            <button
              className="btn btn-sm btn-outline-secondary w-100"
              onClick={() => { setGroupFilter(''); setSearch(''); }}
              disabled={!groupFilter && !search}
            >
              ล้างตัวกรอง
            </button>
          </div>
        </div>
      )}

      <div className="d-flex justify-content-between align-items-center mb-2">
        <label className="text-info small fw-bold">คลิกเลือกรายการที่ต้องการชำแหละข้อมูล (เลือกไว้ {selected.size} · แสดง {options.length}/{allOptions.length}):</label>
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
                <label className="chk-label d-flex align-items-center gap-2 text-white small">
                  <input type="checkbox" className="category-checkbox" checked={selected.has(name)} onChange={() => toggle(name)} />
                  <span className="text-truncate" title={name}>{name}</span>
                </label>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-white-50 small">
            {allOptions.length ? 'ไม่มีข้อหาที่ตรงกับตัวกรอง' : 'กำลังโหลดรายการ...'}
          </div>
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
                    <td className="text-start text-white">
                      <div className="d-flex justify-content-between align-items-center gap-2">
                        <span>{category}</span>
                        <button className="btn btn-sm btn-outline-warning py-0 px-1" title="เปรียบเทียบสองช่วงเวลา"
                                onClick={() => openCompare(category)}>
                          <i className="fa-solid fa-chart-line"></i>
                        </button>
                      </div>
                    </td>
                    {stations.map((s) => {
                      const cell = cells[s.station] || { count: 0, ids: [] };
                      return (
                        <td key={s.station} className="text-center">
                          <button className={`drilldown-btn${cell.count ? '' : ' zero'}`}
                                  onClick={() => openCell(category, cell, s.name)}>
                            {cell.count}
                          </button>
                        </td>
                      );
                    })}
                    <td className="text-center text-warning fw-bold">
                      <button className={`drilldown-btn${cells.total?.count ? '' : ' zero'}`}
                              onClick={() => openCell(category, cells.total, 'ทั้งกองกำกับการ')}>
                        {cells.total?.count ?? 0}
                      </button>
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

      {compare && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setCompare('')}>
          <div className="modal-dialog modal-xl modal-dialog-centered" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-warning">
                  <i className="fa-solid fa-chart-line"></i> เปรียบเทียบข้อมูล: <span className="text-white">{compare}</span>
                </h6>
                <button className="btn-close btn-close-white" onClick={() => setCompare('')}></button>
              </div>
              <div className="modal-body">
                <div className="row g-2 align-items-end mb-3">
                  <div className="col-6 col-md-3">
                    <label className="form-label small text-warning">ช่วงที่ 1 ตั้งแต่</label>
                    <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                           value={cmpRange.s1} onChange={(e) => setCmpRange({ ...cmpRange, s1: e.target.value })} />
                  </div>
                  <div className="col-6 col-md-3">
                    <label className="form-label small text-warning">ถึง</label>
                    <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                           value={cmpRange.e1} onChange={(e) => setCmpRange({ ...cmpRange, e1: e.target.value })} />
                  </div>
                  <div className="col-6 col-md-3">
                    <label className="form-label small text-info">ช่วงที่ 2 ตั้งแต่</label>
                    <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                           value={cmpRange.s2} onChange={(e) => setCmpRange({ ...cmpRange, s2: e.target.value })} />
                  </div>
                  <div className="col-6 col-md-3">
                    <label className="form-label small text-info">ถึง</label>
                    <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                           value={cmpRange.e2} onChange={(e) => setCmpRange({ ...cmpRange, e2: e.target.value })} />
                  </div>
                </div>

                <button className="btn btn-info btn-sm fw-bold mb-3" onClick={runCompare} disabled={cmpBusy}>
                  <i className="fa-solid fa-chart-column"></i> {cmpBusy ? 'กำลังประมวลผล...' : 'ประมวลผลกราฟ'}
                </button>

                {growth && (
                  <div className="mb-3 fw-bold">
                    <span className="text-white-50">{compare}: </span>
                    <span className={growth.cls}><i className={`fa-solid ${growth.icon}`}></i> {growth.text}</span>
                  </div>
                )}

                {cmpData ? (
                  <ReactApexChart
                    type="bar"
                    height={380}
                    options={vBarOptions(cmpData.categories, ['#f59e0b', '#0ea5e9'])}
                    series={cmpData.series.map((s: any) => ({ name: s.label, data: s.data }))}
                  />
                ) : (
                  <div className="text-center py-5 text-white-50">
                    <i className="fa-solid fa-chart-column mb-3" style={{ fontSize: '2rem' }}></i><br />
                    กรุณากด "ประมวลผลกราฟ" เพื่อแสดงข้อมูลเปรียบเทียบ
                  </div>
                )}
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary btn-sm" onClick={() => setCompare('')}>ปิด</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
