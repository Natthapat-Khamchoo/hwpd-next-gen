import React, { useEffect, useMemo, useState } from 'react';
import ReactApexChartImport from 'react-apexcharts';

// react-apexcharts ships as CommonJS; normalize the default export for Vite interop.
const ReactApexChart = ((ReactApexChartImport as any).default ?? ReactApexChartImport) as typeof ReactApexChartImport;
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { DashboardLayout } from './DashboardLayout';
import { DeepSearchModal } from './DeepSearchModal';
import { InvestDashboardPanel } from './InvestDashboardPanel';
import Swal from 'sweetalert2';

const firstOfMonth = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0];
};

const barOptions = (categories: string[]): ApexCharts.ApexOptions => ({
  chart: { type: 'bar', height: 320, toolbar: { show: false }, background: 'transparent' },
  theme: { mode: 'dark' },
  colors: ['#facc15'],
  plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
  dataLabels: { enabled: true, textAnchor: 'start', style: { colors: ['#000'], fontSize: '13px', fontWeight: 'bold' }, offsetX: 15 },
  xaxis: { categories, labels: { style: { colors: '#8b949e' } } },
  yaxis: { labels: { style: { colors: '#fff', fontWeight: 'bold' } } },
  legend: { show: false },
  grid: { borderColor: '#30363d', strokeDashArray: 4 },
  tooltip: { theme: 'dark' },
});
const donutOptions = (labels: string[], colors?: string[]): ApexCharts.ApexOptions => ({
  chart: { type: 'donut', height: 320, background: 'transparent' },
  theme: { mode: 'dark' },
  labels,
  ...(colors ? { colors } : {}),
  legend: { position: 'bottom', labels: { colors: '#fff' } },
  tooltip: { theme: 'dark' },
});

// ไม่รับ onBack เพราะหน้านี้เป็นปลายทางของ Super_Commander ไม่มีเมนูหลักให้กลับไป
export const SuperCommanderDashboard: React.FC<{ onViewDivision?: (station: string, label: string) => void }> = ({ onViewDivision }) => {
  const { user, logout } = useAuth();
  // กก. ที่ตั้งค่าฐานข้อมูลแล้วเท่านั้นที่กดเข้าไปได้ ของเดิมทำตัวที่ยังไม่พร้อมให้จาง
  // และกดไม่ได้ แทนที่จะปล่อยให้กดแล้วเจอหน้าเปล่า
  const [dbHealth, setDbHealth] = useState<Record<string, string>>({});
  useEffect(() => {
    api.getDatabaseHealth(user?.token).then((list) => {
      setDbHealth(Object.fromEntries(list.map((d) => [String(d.division), String(d.status)])));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await api.getNationalSummary(start, end, user?.token);
    setLoading(false);
    if (res.status === 'success') setData(res.data);
    else Swal.fire('เกิดข้อผิดพลาด', res.message || 'โหลดข้อมูลไม่สำเร็จ', 'error');
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ranking = useMemo(() => (data ? [...data.byDivision].sort((a, b) => b.arrestsCount - a.arrestsCount) : []), [data]);
  const totals = data?.totals || {};

  const [searchOpen, setSearchOpen] = useState(false);
  // ผบก. ใช้แดชบอร์ดงานสืบสวนอยู่แล้ว จึงต้องเข้าถึงได้จากที่เดียวกัน
  const [view, setView] = useState<'overview' | 'invest'>('overview');

  const deepSearch = () => {
    setSearchOpen(true);
  };
  const order = async () => {
    const { value } = await Swal.fire({ title: 'สั่งการทั่วประเทศ', input: 'textarea', inputPlaceholder: 'ข้อความคำสั่งการ...', showCancelButton: true, confirmButtonText: 'ส่งคำสั่งการ', confirmButtonColor: '#facc15', cancelButtonText: 'ยกเลิก' });
    if (value) Swal.fire('ส่งคำสั่งการ', 'ข้อความจะถูกส่งเข้า LINE กลุ่มเป้าหมาย (เชื่อมต่อ backend เพื่อส่งจริง)', 'success');
  };

  return (
    <DashboardLayout
      variant="sc"
      bg="sc-bg"
      sidebar={(close) => (
        <>
          <div className="sidebar-header d-flex justify-content-between align-items-center">
            <div>
              <h4 className="text-warning m-0" style={{ textShadow: '0 0 10px rgba(250,204,21,0.5)' }}><i className="fa-solid fa-crown"></i> ผู้บังคับการ</h4>
              <small className="text-white-50">National Executive Command</small>
            </div>
          </div>
          <div className="sidebar-menu">
            <div className={`sidebar-item ${view === 'overview' ? 'active' : ''}`}
                 onClick={() => { close(); setView('overview'); }}>
              <i className="fa-solid fa-earth-asia"></i> ภาพรวมระดับประเทศ (บก.ทล.)
            </div>
            <div className={`sidebar-item ${view === 'invest' ? 'active' : ''}`}
                 onClick={() => { close(); setView('invest'); }}>
              <i className="fa-solid fa-magnifying-glass-chart"></i> แดชบอร์ดงานสืบสวน
            </div>
            <div className="px-4 mt-3 mb-2 small text-warning">เจาะลึกรายกองกำกับ:</div>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((d) => {
              const ready = dbHealth[String(d)] === 'ok';
              // รหัสสถานีของ ฝอ.กก. คือเลข กก. ตามด้วย 0 (กก.7 -> "70") ตรงกับที่ของเดิมส่ง
              return ready ? (
                <div className="sidebar-item text-secondary py-1" key={d}
                     onClick={() => { close(); onViewDivision?.(`${d}0`, `กก.${d}`); }}> กก.{d}</div>
              ) : (
                <div className="sidebar-item text-secondary py-1 opacity-50" key={d}
                     style={{ cursor: 'not-allowed' }} title={`ยังไม่ได้ตั้งค่าฐานข้อมูลของ กก.${d}`}>
                  {' '}กก.{d} <small>(ยังไม่พร้อม)</small>
                </div>
              );
            })}
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
          </div>
        </>
      )}
    >
        {view === 'invest' && <InvestDashboardPanel />}

        {view === 'overview' && (<>
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div className="d-flex align-items-center gap-3">
            {/* ของเดิม super_commander_dashboard.html ไม่มีปุ่มย้อนกลับ หน้านี้คือปลายทาง
                ของบัญชีระดับ บก. ซึ่งใช้เมนูการปฏิบัติงานไม่ได้ (สถานี 00 ไม่มีใน DB_ROUTER) */}
            <div>
              <h3 className="text-white m-0">National Executive Dashboard</h3>
              <p className="text-white-50 small m-0 mt-1">ยินดีต้อนรับ, <span className="text-warning">{user?.fullName}</span></p>
            </div>
          </div>
          <div className="d-flex gap-2 flex-wrap align-items-center">
            <input type="date" className="form-control form-control-sm border-warning bg-dark text-white" style={{ width: 150 }} value={start} onChange={(e) => setStart(e.target.value)} />
            <span className="text-white-50">ถึง</span>
            <input type="date" className="form-control form-control-sm border-warning bg-dark text-white" style={{ width: 150 }} value={end} onChange={(e) => setEnd(e.target.value)} />
            <button className="btn btn-warning btn-sm" onClick={load}><i className="fa-solid fa-magnifying-glass"></i> ดูข้อมูล</button>
            <button className="btn btn-outline-warning btn-sm" onClick={deepSearch}><i className="fa-solid fa-user-secret"></i> ค้นหาทุกกอง</button>
            <button className="btn btn-outline-warning btn-sm" onClick={order}><i className="fa-solid fa-bullhorn"></i> สั่งการ</button>
          </div>
        </div>

        {/* KPIs */}
        <div className="row g-3 mb-4">
          {[
            // arrestsCount นับใบรายงานใน tb_Arrests ส่วน v20Count รวมยอดที่กรอกใน
            // tb_DailyResult คนละเรื่องกัน ป้ายเดิมเขียนว่า "ยอดจับกุม" กับ "รวม ว.20"
            // ซึ่งอ่านแล้วนึกว่าเป็นเรื่องเดียวกัน ใช้คำที่ระบบเดิมใช้ในข้อความ LINE แทน
            { c: 'text-danger', i: 'fa-handcuffs', v: totals.arrestsCount, t: 'จับกุมคดีอาญาทั่วประเทศ' },
            { c: 'text-info', i: 'fa-file-invoice', v: totals.v20Count, t: 'คดีจราจร (ว.20)' },
            { c: 'text-warning', i: 'fa-car-burst', v: totals.accCount, t: 'อุบัติเหตุ' },
            { c: 'text-success', i: 'fa-shield-halved', v: totals.royalCount, t: 'รับเสด็จ' },
            { c: 'text-primary', i: 'fa-bullseye', v: totals.missionCount, t: 'ภารกิจ' },
          ].map((k, idx) => (
            <div className="col-md col-6" key={idx}>
              <div className={`sc-kpi ${k.c}`}>
                <div className="icon"><i className={`fa-solid ${k.i}`}></i></div>
                <div className="value">{k.v ?? 0}</div>
                <div className="title">{k.t}</div>
              </div>
            </div>
          ))}
        </div>

        {loading && <div className="text-center text-warning py-5"><span className="spinner-border"></span></div>}

        {data && (
          <div className="row g-4">
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-ranking-star"></i> จัดอันดับผลปฏิบัติ 8 กก. (จับกุม)</h5>
                <ReactApexChart type="bar" height={320} options={barOptions(ranking.map((d) => d.divName))} series={[{ name: 'คดีอาญา', data: ranking.map((d) => d.arrestsCount) }]} />
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-chart-line"></i> เทรนด์รายวันทั่วประเทศ</h5>
                <ReactApexChart type="line" height={320} options={{ chart: { type: 'line', height: 320, toolbar: { show: false }, background: 'transparent' }, theme: { mode: 'dark' }, colors: ['#facc15', '#ef4444'], stroke: { curve: 'smooth', width: 3 }, xaxis: { categories: data.trend.map((t: any) => t.date), labels: { style: { colors: '#8b949e' } } }, yaxis: { labels: { style: { colors: '#8b949e' } } }, legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#fff' } }, grid: { borderColor: '#30363d', strokeDashArray: 4 }, tooltip: { theme: 'dark' } }} series={[{ name: 'คดีอาญา', data: data.trend.map((t: any) => t.arrestsCount) }, { name: 'อุบัติเหตุ', data: data.trend.map((t: any) => t.accCount) }]} />
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-handcuffs"></i> สัดส่วนประเภทคดีจับกุมทั่วประเทศ</h5>
                <ReactApexChart type="donut" height={320} options={donutOptions(Object.keys(data.arrestTypeBreakdown))} series={Object.values(data.arrestTypeBreakdown) as number[]} />
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-table-list"></i> ตารางจัดอันดับ กก.</h5>
                <div className="table-responsive">
                  <table className="table table-sc table-bordered text-center align-middle">
                    <thead><tr><th>ลำดับ</th><th className="text-start">กก.</th><th>คดีอาญา</th><th>คดีจราจร</th><th>อุบัติเหตุ</th><th>ภารกิจ</th></tr></thead>
                    <tbody>
                      {ranking.map((d, i) => (
                        <tr key={d.div}><td className={`fw-bold ${i === 0 ? 'text-warning' : ''}`}>{i + 1}</td><td className="text-start">{d.divName}</td><td>{d.arrestsCount}</td><td>{d.v20Count}</td><td>{d.accCount}</td><td>{d.missionCount}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-gavel"></i> สัดส่วนข้อหาทั่วประเทศ</h5>
                <ReactApexChart type="bar" height={320} options={barOptions(Object.keys(data.chargeBreakdown))} series={[{ name: 'จำนวน', data: Object.values(data.chargeBreakdown) as number[] }]} />
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-car-burst"></i> สาเหตุอุบัติเหตุทั่วประเทศ</h5>
                <ReactApexChart type="donut" height={320} options={donutOptions(['คน', 'ยานพาหนะ', 'ถนน', 'สิ่งแวดล้อม'], ['#facc15', '#fbbf24', '#f59e0b', '#d97706'])} series={[data.accCauseBreakdown.human, data.accCauseBreakdown.vehicle, data.accCauseBreakdown.road, data.accCauseBreakdown.env]} />
              </div>
            </div>
          </div>
        )}
        </>)}

        {searchOpen && <DeepSearchModal scope="national" onClose={() => setSearchOpen(false)} />}
    </DashboardLayout>
  );
};
