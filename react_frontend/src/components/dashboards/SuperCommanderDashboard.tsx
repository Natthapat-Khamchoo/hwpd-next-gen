import React, { useEffect, useMemo, useState } from 'react';
import ReactApexChartImport from 'react-apexcharts';

// react-apexcharts ships as CommonJS; normalize the default export for Vite interop.
const ReactApexChart = ((ReactApexChartImport as any).default ?? ReactApexChartImport) as typeof ReactApexChartImport;
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
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

export const SuperCommanderDashboard: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user, logout } = useAuth();
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

  const deepSearch = async () => {
    const { value } = await Swal.fire({ title: 'แกะรอยผลงานทั่วประเทศ', input: 'text', inputPlaceholder: 'พิมพ์ชื่อ, ทะเบียนรถ, คีย์เวิร์ด...', showCancelButton: true, confirmButtonText: 'ค้นหา', confirmButtonColor: '#facc15', cancelButtonText: 'ปิด' });
    if (value) Swal.fire('ค้นหาทุกกอง', `ระบบจะสแกน 7 ฐานข้อมูลทั่ว 8 กก. หา "${value}" (เชื่อมต่อ backend เพื่อดูผลจริง)`, 'info');
  };
  const order = async () => {
    const { value } = await Swal.fire({ title: 'สั่งการทั่วประเทศ', input: 'textarea', inputPlaceholder: 'ข้อความคำสั่งการ...', showCancelButton: true, confirmButtonText: 'ส่งคำสั่งการ', confirmButtonColor: '#facc15', cancelButtonText: 'ยกเลิก' });
    if (value) Swal.fire('ส่งคำสั่งการ', 'ข้อความจะถูกส่งเข้า LINE กลุ่มเป้าหมาย (เชื่อมต่อ backend เพื่อส่งจริง)', 'success');
  };

  return (
    <div className="dashboard-wrapper sc-bg animate-fade-in">
      {/* Sidebar */}
      <div className="dash-sidebar sc">
        <div className="sidebar-header d-flex justify-content-between align-items-center">
          <div>
            <h4 className="text-warning m-0" style={{ textShadow: '0 0 10px rgba(250,204,21,0.5)' }}><i className="fa-solid fa-crown"></i> ผู้บังคับการ</h4>
            <small className="text-white-50">National Executive Command</small>
          </div>
        </div>
        <div className="sidebar-menu">
          <div className="sidebar-item active"><i className="fa-solid fa-earth-asia"></i> ภาพรวมระดับประเทศ (บก.ทล.)</div>
          <div className="px-4 mt-3 mb-2 small text-warning">เจาะลึกรายกองกำกับ:</div>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((d) => (
            <div className="sidebar-item text-secondary py-1" key={d} onClick={() => Swal.fire('เจาะลึก กก.' + d, 'เปิดหน้าผู้กำกับการของ กก.' + d + ' (พอร์ตหน้า commander ต่อไป)', 'info')}> กก.{d}</div>
          ))}
        </div>
        <div className="mt-auto border-top border-secondary p-3">
          <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
        </div>
      </div>

      {/* Main */}
      <div className="main-content">
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div className="d-flex align-items-center gap-3">
            <button className="btn btn-outline-warning btn-sm" onClick={onBack}><i className="fa-solid fa-arrow-left"></i></button>
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
            { c: 'text-danger', i: 'fa-handcuffs', v: totals.arrestsCount, t: 'ยอดจับกุมทั่วประเทศ' },
            { c: 'text-info', i: 'fa-file-invoice', v: totals.v20Count, t: 'รวม ว.20' },
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
                <ReactApexChart type="bar" height={320} options={barOptions(ranking.map((d) => d.divName))} series={[{ name: 'จับกุม', data: ranking.map((d) => d.arrestsCount) }]} />
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="glass-card"><h5 className="text-warning mb-3"><i className="fa-solid fa-chart-line"></i> เทรนด์รายวันทั่วประเทศ</h5>
                <ReactApexChart type="line" height={320} options={{ chart: { type: 'line', height: 320, toolbar: { show: false }, background: 'transparent' }, theme: { mode: 'dark' }, colors: ['#facc15', '#ef4444'], stroke: { curve: 'smooth', width: 3 }, xaxis: { categories: data.trend.map((t: any) => t.date), labels: { style: { colors: '#8b949e' } } }, yaxis: { labels: { style: { colors: '#8b949e' } } }, legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#fff' } }, grid: { borderColor: '#30363d', strokeDashArray: 4 }, tooltip: { theme: 'dark' } }} series={[{ name: 'จับกุม', data: data.trend.map((t: any) => t.arrestsCount) }, { name: 'อุบัติเหตุ', data: data.trend.map((t: any) => t.accCount) }]} />
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
                    <thead><tr><th>ลำดับ</th><th className="text-start">กก.</th><th>จับกุม</th><th>ว.20</th><th>อุบัติเหตุ</th><th>ภารกิจ</th></tr></thead>
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
      </div>
    </div>
  );
};
