import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { DashboardLayout, SideItem } from './DashboardLayout';
import { recentStart } from './hq/panelHelpers';
import { FuelPanel } from './hq/FuelPanel';
import { ManpowerPanel } from './hq/ManpowerPanel';
import { EvidencePanel } from './hq/EvidencePanel';
import { EscortPanel } from './hq/EscortPanel';
import { DailyDetailPanel } from './hq/DailyDetailPanel';
import { SearchPanel } from './hq/SearchPanel';
import { AnalysisPanel } from './hq/AnalysisPanel';
import { MapPanelLazy } from './hq/MapPanelLazy';
import { PrPanel } from './hq/PrPanel';


/**
 * แถวในตารางภาพรวม ตรงกับ createRow ใน loadHQOverview ของต้นฉบับทั้งลำดับ ป้าย และสี
 * ยอดรวมท้ายแถวอ่านจาก totals ไม่ใช่บวกจากรายสถานีเอง เพราะสองค่านี้ต้องมาจากการนับ
 * ชุดเดียวกัน ไม่งั้นถ้ามีรายงานของสถานีที่ไม่อยู่ในรายการ ตัวเลขจะไม่ตรงกัน
 */
const OVERVIEW_ROWS = [
  { label: 'ว.43 (ครั้ง)', icon: 'fa-road', key: 'v43', cls: 'text-primary' },
  { label: 'ว.20 (ครั้ง)', icon: 'fa-file-invoice', key: 'v20', cls: 'text-warning' },
  { label: 'รายงานจับกุม (คดี)', icon: 'fa-handcuffs', key: 'arrest', cls: 'text-danger' },
  { label: 'จิตอาสา (ครั้ง)', icon: 'fa-hands-holding-child', key: 'volunteer', cls: 'text-info' },
  { label: 'รับเสด็จ (ครั้ง)', icon: 'fa-shield-halved', key: 'royalGuard', cls: 'text-success' },
] as const;

// ตรงกับตัวแปร titles ใน loadHqView ของต้นฉบับ
const VIEW_TITLES: Record<string, string> = {
  overview: 'ภาพรวมผลการปฏิบัติ',
  search: 'ระบบสืบค้นข้อมูลเชิงลึก',
  fuel: 'ระบบจัดการน้ำมัน/น้ำมันเครื่อง',
  daily_detail: 'แฟ้มข้อมูลและส่งออก Excel',
  manpower: 'ระบบจัดการกำลังพลส่วนกลาง',
  evidence: 'ระบบจัดหมวดหมู่ของกลาง',
  escort: 'ระบบจัดการการนำขบวน',
  map: 'แผนที่ผลการปฏิบัติ',
  pr: 'งานประชาสัมพันธ์',
};

interface HqDashboardProps {
  onBack: () => void;
  /**
   * ส่งมาเมื่อผู้กำกับการกดเข้ามาจากหน้าตัวเอง — ของเดิมสลับป้ายปุ่มในเมนูข้างเป็น
   * "กลับหน้าผู้กำกับการ" แล้วคืนค่าเดิมตอนออก (cmdSwitchToHQ)
   */
  onBackToCommander?: () => void;
}

export const HqDashboard: React.FC<HqDashboardProps> = ({ onBack, onBackToCommander }) => {
  const { user, logout } = useAuth();
  const div = String(user?.station || '5').charAt(0);
  const [view, setView] = useState('overview');
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);
  const [loadError, setLoadError] = useState('');
  const [reports, setReports] = useState<{ reportKey: string; title: string; cadence: string }[]>([]);
  const station = user?.station || '';

  // ผกก. ได้หน้านี้เต็มรูปแบบเหมือน ฝอ. เพราะ cmdSwitchToHQ ของเดิมเปิด hqDashboard
  // ตัวเดียวกันโดยไม่เช็ค role เลย ที่กันออกคือระดับสถานีซึ่งเข้าหน้านี้ไม่ได้อยู่แล้ว
  const canEdit = true;
  // ตัวออก Excel รวมยอดทั้ง 8 กก. ไว้ในไฟล์เดียว ระดับ กก. จึงเรียกไม่ได้ (API ตอบ 403)
  // ถ้าไม่กันไว้ตรงนี้ หน้าจะขึ้นว่า "ยังไม่มีแบบฟอร์ม" ซึ่งอ่านเหมือนระบบเสีย
  const canExport = user?.role === 'HQ_Admin' || user?.role === 'Super_Commander';

  const load = async () => {
    const res = await api.getDivisionSummary(station, start, end, user?.token);
    // เหมือนหน้าผู้กำกับการ — เงียบแล้วโชว์ 0 อันตรายกว่าบอกตรง ๆ ว่าโหลดไม่สำเร็จ
    if (res.status === 'success') { setData(res.data); setLoadError(''); }
    else setLoadError(res.message || 'โหลดข้อมูลไม่สำเร็จ');
  };
  useEffect(() => {
    load();
    if (canExport) api.getExportableReports(user?.token).then(setReports);
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  const t = data?.totals || {};
  const bs = data?.byStation || [];

  const nav = (id: string, close: () => void) => { setView(id); close(); };

  // ห้าใบ เรียงตามต้นฉบับ (kpi-v43 / v20 / arrest / volunteer / royalGuard)
  // ของเดิมไม่มีการ์ด "บริการ" ในหน้านี้ ยอดบริการไปอยู่ในรายงานสรุปแทน
  const kpis = [
    { c: 'text-primary', i: 'fa-road', v: t.v43, l: 'รวม ว.43' },
    // v20 คือยอดคดีจราจรที่กรอกในผลการปฏิบัติประจำวัน ส่วน arrest นับใบรายงานจับกุม
    // (คดีอาญา) ใช้คำเดียวกับข้อความ LINE ของระบบเดิมเพื่อไม่ให้อ่านสับสน
    { c: 'text-warning', i: 'fa-file-invoice', v: t.v20, l: 'รวม ว.20' },
    { c: 'text-danger', i: 'fa-handcuffs', v: t.arrest, l: 'รายงานจับกุม' },
    { c: 'text-info', i: 'fa-hands-holding-child', v: t.volunteer, l: 'รวม จิตอาสา' },
    { c: 'text-success', i: 'fa-shield-halved', v: t.royalGuard, l: 'รวม รับเสด็จ' },
  ];

  return (
    <DashboardLayout
      bg="hq-bg"
      sidebar={(close) => (
        <>
          <div className="sidebar-header"><h4 className="text-white m-0" style={{ textShadow: '0 0 10px #38bdf8' }}>กองกำกับการ {div}</h4><small className="text-white-50">ฝอ.กก.{div}</small></div>
          <div className="sidebar-menu">
            <SideItem icon="fa-chart-line" active={view === 'overview'} onClick={() => nav('overview', close)}>ภาพรวมผลการปฏิบัติ</SideItem>
            <SideItem icon="fa-magnifying-glass" active={view === 'search'} onClick={() => nav('search', close)}>ระบบสืบค้นฐานข้อมูล</SideItem>
            <SideItem icon="fa-map-location-dot" cls="text-danger" active={view === 'map'} onClick={() => nav('map', close)}>แผนที่ผลการปฏิบัติ</SideItem>
            <SideItem icon="fa-gas-pump" active={view === 'fuel'} onClick={() => nav('fuel', close)}>ระบบจัดการน้ำมัน</SideItem>
            <SideItem icon="fa-folder-open" cls="text-success" active={view === 'daily_detail'} onClick={() => nav('daily_detail', close)}>แฟ้มข้อมูล / ส่งออก Excel</SideItem>
            <SideItem icon="fa-users" cls="text-primary" active={view === 'manpower'} onClick={() => nav('manpower', close)}>ระบบจัดการกำลังพล</SideItem>
            <SideItem icon="fa-boxes-packing" cls="text-warning" active={view === 'evidence'} onClick={() => nav('evidence', close)}>จัดหมวดหมู่ของกลาง</SideItem>
            <SideItem icon="fa-motorcycle" cls="text-info" active={view === 'escort'} onClick={() => nav('escort', close)}>ระบบจัดการการนำขบวน</SideItem>
            <SideItem icon="fa-bullhorn" cls="text-warning" active={view === 'pr'} onClick={() => nav('pr', close)}>งานประชาสัมพันธ์</SideItem>
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            {onBackToCommander ? (
              <div className="sidebar-item text-warning" onClick={onBackToCommander}>
                <i className="fa-solid fa-star"></i> กลับหน้าผู้กำกับการ
              </div>
            ) : (
              <div className="sidebar-item text-warning" onClick={onBack}>
                <i className="fa-solid fa-rotate"></i> กลับเมนูหลัก
              </div>
            )}
            <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
          </div>
        </>
      )}
    >
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div><h3 className="text-white m-0">{VIEW_TITLES[view]} กก.{div}</h3><p className="text-white-50 small m-0">ยินดีต้อนรับ, <span className="text-info">{user?.fullName}</span></p></div>
          {view === 'overview' && (
            <div className="d-flex flex-wrap align-items-center gap-2">
              <input type="date" className="form-control form-control-sm bg-dark text-white border-info" style={{ width: 150 }} value={start} onChange={(e) => setStart(e.target.value)} />
              <span className="text-white-50">ถึง</span>
              <input type="date" className="form-control form-control-sm bg-dark text-white border-info" style={{ width: 150 }} value={end} onChange={(e) => setEnd(e.target.value)} />
              <button className="btn btn-info btn-sm fw-bold" onClick={load}><i className="fa-solid fa-chart-pie"></i> ประมวลผล</button>
            </div>
          )}
        </div>

        {view === 'overview' && loadError && (
          <div className="alert alert-danger d-flex justify-content-between align-items-center py-2 mb-4">
            <span><i className="fa-solid fa-triangle-exclamation"></i> {loadError} — ตัวเลขด้านล่างยังไม่ใช่ข้อมูลจริง</span>
            <button className="btn btn-sm btn-outline-light" onClick={load}>ลองใหม่</button>
          </div>
        )}

        {view === 'overview' && data && (
          <>
            <div className="glass-card mb-4">
              <h5 className="text-white mb-3"><i className="fa-solid fa-crown text-warning"></i> สรุปผลการปฏิบัติภาพรวม กก.{div} (เทียบรายสถานี)</h5>
              <div className="row g-3 mb-3">
                {kpis.map((k, i) => <div className="col-md-2 col-6" key={i}><div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}><div className="title"><i className={`fa-solid ${k.i}`}></i> {k.l}</div><div className={`value ${k.c}`}>{k.v ?? '-'}</div></div></div>)}
              </div>
              <div className="table-responsive">
                <table className="table table-hq table-bordered text-center align-middle">
                  <thead>
                    <tr>
                      <th className="text-start" style={{ width: '16%' }}>ประเภทการปฏิบัติ</th>
                      {bs.map((s: any) => <th key={s.station} className="text-white-50">{s.name}</th>)}
                      <th style={{ color: '#facc15' }}>รวม กก.{div}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {OVERVIEW_ROWS.map(({ label, icon, key, cls }) => (
                      <tr key={key} className={`text-center ${cls}`}>
                        <td className="text-start fw-bold"><i className={`fa-solid ${icon}`}></i> {label}</td>
                        {bs.map((s: any) => <td key={s.station}>{s[key] ?? 0}</td>)}
                        <td className="fw-bold" style={{ color: '#facc15' }}>{t[key] ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <AnalysisPanel station={station} start={start} end={end}
                           stations={bs.map((s: any) => ({ station: String(s.station), name: s.name }))} />

          </>
        )}

        {view === 'search' && <SearchPanel station={station} />}
        {view === 'map' && (
          <MapPanelLazy station={station} stations={bs.map((s: any) => ({ station: String(s.station), name: s.name }))} />
        )}
        {view === 'fuel' && <FuelPanel station={station} canEdit={canEdit} />}
        {view === 'daily_detail' && <DailyDetailPanel station={station} reports={reports} canExport={canExport} />}
        {view === 'manpower' && <ManpowerPanel station={station} canEdit={canEdit} />}
        {view === 'evidence' && <EvidencePanel station={station} canEdit={canEdit} />}
        {view === 'escort' && <EscortPanel station={station} canEdit={canEdit} />}
        {view === 'pr' && <PrPanel station={station} canDecide={canEdit} />}
    </DashboardLayout>
  );
};
