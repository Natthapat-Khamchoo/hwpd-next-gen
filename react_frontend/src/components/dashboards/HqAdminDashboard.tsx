import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { ReactApexChart, vBarOptions } from './chartHelpers';
import { DashboardLayout, SideItem } from './DashboardLayout';

const firstOfMonth = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0]; };

const VIEW_TITLES: Record<string, string> = {
  compare: 'เปรียบเทียบผลปฏิบัติระดับประเทศ',
  users: 'จัดการข้อมูลผู้ใช้งาน (ทุก กก.)',
  import: 'นำเข้า/จัดการข้อมูลสถานี',
  charges: 'จัดการฐานข้อมูลข้อหา (tb_Charges)',
  items: 'จัดการประเภทของกลาง (tb_SeizedItemTypes)',
  reports: 'ตั้งค่ารูปแบบรายงาน',
  center: 'ศูนย์ควบคุมส่วนกลาง',
  cases: 'ระบบบริหารคดีสำคัญ',
};

// ไม่รับ onBack เพราะหน้านี้เป็นปลายทางของ HQ_Admin ไม่มีเมนูหลักให้กลับไป
export const HqAdminDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [view, setView] = useState('compare');
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);

  const load = async () => {
    const res = await api.getNationalSummary(start, end, user?.token);
    if (res.status === 'success') setData(res.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const ranking = useMemo(() => (data ? [...data.byDivision].sort((a, b) => b.arrestsCount - a.arrestsCount) : []), [data]);

  const nav = (id: string, close: () => void) => { setView(id); close(); };

  return (
    <DashboardLayout
      variant="hqa"
      bg="hqa-bg"
      sidebar={(close) => (
        <>
          <div className="sidebar-header"><h4 className="text-white m-0" style={{ textShadow: '0 0 10px #a855f7' }}>บก.ทล.</h4><small className="text-white-50">ฝ่ายอำนวยการ (ส่วนกลาง)</small></div>
          <div className="sidebar-menu">
            <SideItem icon="fa-chart-column" active={view === 'compare'} onClick={() => nav('compare', close)}>เปรียบเทียบผลปฏิบัติ</SideItem>
            <SideItem icon="fa-users-gear" active={view === 'users'} onClick={() => nav('users', close)}>จัดการผู้ใช้งาน</SideItem>
            <SideItem icon="fa-file-import" active={view === 'import'} onClick={() => nav('import', close)}>จัดการข้อมูลสถานี</SideItem>
            <SideItem icon="fa-gavel" active={view === 'charges'} onClick={() => nav('charges', close)}>จัดการข้อหา</SideItem>
            <SideItem icon="fa-boxes-packing" active={view === 'items'} onClick={() => nav('items', close)}>ประเภทของกลาง</SideItem>
            <SideItem icon="fa-file-lines" active={view === 'reports'} onClick={() => nav('reports', close)}>ตั้งค่ารายงาน</SideItem>
            <SideItem icon="fa-tower-broadcast" active={view === 'center'} onClick={() => nav('center', close)}>ศูนย์ควบคุมส่วนกลาง</SideItem>
            <SideItem icon="fa-folder-tree" active={view === 'cases'} onClick={() => nav('cases', close)}>บริหารคดีสำคัญ</SideItem>
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            {/* ของเดิม hq_admin_dashboard.html ไม่มีปุ่มกลับเมนูหลัก และบัญชีระดับ บก.
                ใช้เมนูนั้นไม่ได้อยู่แล้วเพราะสถานี 00 ไม่มีใน DB_ROUTER */}
            <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
          </div>
        </>
      )}
    >
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div><h3 className="text-white m-0">{VIEW_TITLES[view]}</h3><p className="text-white-50 small m-0">ยินดีต้อนรับ, <span style={{ color: '#c084fc' }}>{user?.fullName}</span></p></div>
          {view === 'compare' && (
            <div className="d-flex flex-wrap align-items-center gap-2">
              <input type="date" className="form-control form-control-sm bg-dark text-white" style={{ width: 150, borderColor: '#a855f7' }} value={start} onChange={(e) => setStart(e.target.value)} />
              <span className="text-white-50">ถึง</span>
              <input type="date" className="form-control form-control-sm bg-dark text-white" style={{ width: 150, borderColor: '#a855f7' }} value={end} onChange={(e) => setEnd(e.target.value)} />
              <button className="btn btn-sm fw-bold text-white" style={{ background: '#a855f7' }} onClick={load}><i className="fa-solid fa-chart-pie"></i> ประมวลผล</button>
            </div>
          )}
        </div>

        {view === 'compare' && data && (
          <div className="row g-4">
            <div className="col-12 col-lg-7"><div className="glass-card h-100"><h5 className="text-white mb-3"><i className="fa-solid fa-chart-column" style={{ color: '#c084fc' }}></i> เปรียบเทียบผลปฏิบัติ 8 กองกำกับการ</h5>
              <ReactApexChart type="bar" height={340} options={vBarOptions(ranking.map((d) => d.divName), ['#a855f7', '#ef4444', '#0dcaf0'])} series={[{ name: 'จับกุม', data: ranking.map((d) => d.arrestsCount) }, { name: 'อุบัติเหตุ', data: ranking.map((d) => d.accCount) }, { name: 'ว.20', data: ranking.map((d) => d.v20Count) }]} /></div></div>
            <div className="col-12 col-lg-5"><div className="glass-card h-100"><h5 className="text-white mb-3"><i className="fa-solid fa-ranking-star" style={{ color: '#c084fc' }}></i> ตารางจัดอันดับ</h5>
              <div className="table-responsive"><table className="table table-sc table-bordered text-center align-middle"><thead><tr><th>#</th><th className="text-start">กก.</th><th>จับกุม</th><th>ว.20</th></tr></thead><tbody>{ranking.map((d, i) => <tr key={d.div}><td className="fw-bold">{i + 1}</td><td className="text-start">{d.divName}</td><td>{d.arrestsCount}</td><td>{d.v20Count}</td></tr>)}</tbody></table></div>
            </div></div>
          </div>
        )}

        {view !== 'compare' && (
          <div className="glass-card w-100 p-4 text-center py-5">
            <i className="fa-solid fa-database mb-3" style={{ fontSize: '2.5rem', color: '#c084fc' }}></i>
            <h5 className="text-white">{VIEW_TITLES[view]}</h5>
            <p className="text-white-50 mb-0">โครงหน้าตรงตามต้นฉบับแล้ว — ส่วนจัดการข้อมูลพร้อมทำงานเมื่อเชื่อมต่อ Backend (FastAPI)</p>
          </div>
        )}
    </DashboardLayout>
  );
};
