import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { ReactApexChart, vBarOptions, donutOptions } from './chartHelpers';
import { DashboardLayout, SideItem } from './DashboardLayout';

const firstOfMonth = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0]; };

const VIEW_TITLES: Record<string, string> = {
  overview: 'ภาพรวมผลการปฏิบัติ',
  search: 'ระบบสืบค้นฐานข้อมูล',
  fuel: 'ระบบควบคุมโควตาน้ำมัน/น้ำมันเครื่อง',
  daily_detail: 'แฟ้มข้อมูล / ส่งออก Excel',
  manpower: 'ภาพรวมกำลังพลระดับกองกำกับการ',
  evidence: 'ตารางจัดหมวดหมู่ของกลาง (ฝอ.)',
  escort: 'ระบบจัดการการนำขบวน (ฝอ.)',
};

export const HqDashboard: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user, logout } = useAuth();
  const div = String(user?.station || '5').charAt(0);
  const [view, setView] = useState('overview');
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);

  const load = async () => {
    const res = await api.getDivisionSummary(user?.station || '', start, end, user?.token);
    if (res.status === 'success') setData(res.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const t = data?.totals || {};
  const bs = data?.byStation || [];

  const nav = (id: string, close: () => void) => { setView(id); close(); };

  const kpis = [
    { c: 'text-primary', i: 'fa-road', v: t.v43, l: 'รวม ว.43' },
    { c: 'text-warning', i: 'fa-file-invoice', v: t.v20, l: 'รวม ว.20' },
    { c: 'text-danger', i: 'fa-handcuffs', v: t.arrest, l: 'จับกุม' },
    { c: 'text-info', i: 'fa-hands-holding-child', v: t.volunteer, l: 'จิตอาสา' },
    { c: 'text-success', i: 'fa-shield-halved', v: t.royalGuard, l: 'รับเสด็จ' },
    { c: 'text-secondary', i: 'fa-car-side', v: t.service, l: 'บริการ' },
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
            <SideItem icon="fa-gas-pump" active={view === 'fuel'} onClick={() => nav('fuel', close)}>ระบบจัดการน้ำมัน</SideItem>
            <SideItem icon="fa-folder-open" cls="text-success" active={view === 'daily_detail'} onClick={() => nav('daily_detail', close)}>แฟ้มข้อมูล / ส่งออก Excel</SideItem>
            <SideItem icon="fa-users" cls="text-primary" active={view === 'manpower'} onClick={() => nav('manpower', close)}>ระบบจัดการกำลังพล</SideItem>
            <SideItem icon="fa-boxes-packing" cls="text-warning" active={view === 'evidence'} onClick={() => nav('evidence', close)}>จัดหมวดหมู่ของกลาง</SideItem>
            <SideItem icon="fa-motorcycle" cls="text-info" active={view === 'escort'} onClick={() => nav('escort', close)}>ระบบจัดการการนำขบวน</SideItem>
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            <div className="sidebar-item text-warning" onClick={onBack}><i className="fa-solid fa-rotate"></i> กลับเมนูหลัก</div>
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

        {view === 'overview' && data && (
          <>
            <div className="glass-card mb-4">
              <h5 className="text-white mb-3"><i className="fa-solid fa-crown text-warning"></i> สรุปผลการปฏิบัติภาพรวม กก.{div} (เทียบรายสถานี)</h5>
              <div className="row g-3 mb-3">
                {kpis.map((k, i) => <div className="col-md-2 col-6" key={i}><div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}><div className="title"><i className={`fa-solid ${k.i}`}></i> {k.l}</div><div className={`value ${k.c}`}>{k.v ?? '-'}</div></div></div>)}
              </div>
              <div className="table-responsive">
                <table className="table table-hq table-bordered text-center align-middle">
                  <thead><tr><th className="text-start">ประเภทการปฏิบัติ</th>{bs.map((s: any) => <th key={s.station} className="text-white-50">{s.name}</th>)}<th className="text-warning">รวม</th></tr></thead>
                  <tbody>
                    {([['ว.43', 'v43'], ['ว.20', 'v20'], ['จับกุม', 'arrest'], ['บริการ', 'service'], ['รับเสด็จ', 'royalGuard']] as const).map(([label, key]) => (
                      <tr key={key}><td className="text-start">{label}</td>{bs.map((s: any) => <td key={s.station}>{s[key]}</td>)}<td className="text-warning fw-bold">{bs.reduce((a: number, s: any) => a + s[key], 0)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="row g-4">
              <div className="col-12 col-lg-7"><div className="glass-card h-100"><h5 className="text-white mb-3"><i className="fa-solid fa-chart-column text-info"></i> เปรียบเทียบผลปฏิบัติรายสถานี</h5>
                <ReactApexChart type="bar" height={320} options={vBarOptions(bs.map((s: any) => s.name), ['#ef4444', '#ffc107', '#20c997'])} series={[{ name: 'จับกุม', data: bs.map((s: any) => s.arrest) }, { name: 'ว.20', data: bs.map((s: any) => s.v20) }, { name: 'รับเสด็จ', data: bs.map((s: any) => s.royalGuard) }]} /></div></div>
              <div className="col-12 col-lg-5"><div className="glass-card h-100"><h5 className="text-white mb-3"><i className="fa-solid fa-boxes-packing text-warning"></i> หมวดหมู่ของกลาง</h5>
                <ReactApexChart type="donut" height={320} options={donutOptions(Object.keys(data.seizedBreakdown))} series={Object.values(data.seizedBreakdown) as number[]} /></div></div>
            </div>
          </>
        )}

        {view !== 'overview' && (
          <div className="glass-card w-100 p-4 text-center py-5">
            <i className="fa-solid fa-database text-info mb-3" style={{ fontSize: '2.5rem' }}></i>
            <h5 className="text-white">{VIEW_TITLES[view]}</h5>
            <p className="text-white-50 mb-0">โครงหน้าตรงตามต้นฉบับแล้ว — ส่วนนี้พร้อมแสดงผลเมื่อเชื่อมต่อกับ Backend (FastAPI)</p>
          </div>
        )}
    </DashboardLayout>
  );
};
