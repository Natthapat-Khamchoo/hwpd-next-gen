import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { ReactApexChart, hBarOptions, vBarOptions, donutOptions } from './chartHelpers';
import Swal from 'sweetalert2';

const firstOfMonth = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0]; };

interface Props { onBack: () => void; onSwitchHQ?: () => void }

export const CommanderDashboard: React.FC<Props> = ({ onBack, onSwitchHQ }) => {
  const { user, logout } = useAuth();
  const div = String(user?.station || '5').charAt(0);
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);
  const [msg, setMsg] = useState('');
  const [target, setTarget] = useState('ALL');

  const load = async () => {
    const res = await api.getDivisionSummary(user?.station || '', start, end, user?.token);
    if (res.status === 'success') setData(res.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const t = data?.totals || {};
  const bs = data?.byStation || [];

  const sendOrder = async () => {
    if (!msg.trim()) return Swal.fire('แจ้งเตือน', 'กรุณาพิมพ์ข้อความก่อน', 'warning');
    Swal.fire('ถ่ายทอดคำสั่ง', `ส่งข้อความไปยัง ${target === 'ALL' ? `ทุกสถานี (กก.${div})` : 'ส.ทล.' + target.charAt(1)} (เชื่อมต่อ backend เพื่อส่งจริง)`, 'success');
    setMsg('');
  };

  const kpis = [
    { c: 'text-danger', i: 'fa-handcuffs', v: t.arrest, l: 'จับกุม' },
    { c: 'text-warning', i: 'fa-file-invoice', v: t.v20, l: 'ว.20' },
    { c: 'text-primary', i: 'fa-road', v: t.v43, l: 'ว.43' },
    { c: 'text-info', i: 'fa-hands-holding-child', v: t.volunteer, l: 'จิตอาสา' },
    { c: 'text-success', i: 'fa-shield-halved', v: t.royalGuard, l: 'รับเสด็จ' },
    { c: 'text-secondary', i: 'fa-bullseye', v: t.mission, l: 'ภารกิจ' },
  ];

  return (
    <div className="dashboard-wrapper sc-bg animate-fade-in">
      <div className="dash-sidebar sc">
        <div className="sidebar-header">
          <h4 className="text-warning m-0" style={{ textShadow: '0 0 10px rgba(250,204,21,0.5)' }}><i className="fa-solid fa-star"></i> ผู้กำกับการ</h4>
          <small className="text-white-50">Executive Command · กก.{div}</small>
        </div>
        <div className="sidebar-menu">
          <div className="sidebar-item active"><i className="fa-solid fa-chart-line"></i> ภาพรวมระดับบริหาร (Executive)</div>
          <h6 className="text-white-50 px-4 mt-4 mb-2 small"><i className="fa-solid fa-sitemap"></i> ทางลัดการเข้าถึงระบบ</h6>
          {onSwitchHQ && <div className="sidebar-item text-info" onClick={onSwitchHQ}><i className="fa-solid fa-building-shield"></i> เข้าสู่หน้า ฝอ. (HQ Dashboard)</div>}
          <div className="px-4 mt-3 mb-2 small text-warning">เจาะลึกรายสถานี:</div>
          {bs.map((s: any) => <div className="sidebar-item text-secondary py-1" key={s.station} onClick={() => Swal.fire('เจาะลึก ' + s.name, 'ดูรายละเอียดสถานี ' + s.name, 'info')}> {s.name}</div>)}
        </div>
        <div className="mt-auto border-top border-secondary p-3">
          <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
        </div>
      </div>

      <div className="main-content">
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div className="d-flex align-items-center gap-3">
            <button className="btn btn-outline-warning btn-sm" onClick={onBack}><i className="fa-solid fa-arrow-left"></i></button>
            <div><h3 className="text-white m-0">Executive Dashboard</h3><p className="text-white-50 small m-0 mt-1">ยินดีต้อนรับ, <span className="text-warning">{user?.fullName}</span></p></div>
          </div>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <input type="date" className="form-control form-control-sm bg-dark text-white border-warning" style={{ width: 150 }} value={start} onChange={(e) => setStart(e.target.value)} />
            <span className="text-white-50 fw-bold">-</span>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-warning" style={{ width: 150 }} value={end} onChange={(e) => setEnd(e.target.value)} />
            <button className="btn btn-warning fw-bold px-3" onClick={load}><i className="fa-solid fa-rotate"></i></button>
            <button className="btn btn-info fw-bold px-3" onClick={() => Swal.fire('แกะรอยผลงาน', 'ค้นหาผลงานเจ้าหน้าที่ในกอง (เชื่อมต่อ backend)', 'info')}><i className="fa-solid fa-user-secret"></i> แกะรอยผลงาน</button>
          </div>
        </div>

        {/* Command Center */}
        <div className="glass-card mb-4" style={{ borderColor: 'rgba(13,202,240,0.4)' }}>
          <h5 className="text-info mb-3"><i className="fa-solid fa-walkie-talkie"></i> ศูนย์สั่งการผู้บังคับบัญชา (Command Center)</h5>
          <div className="row g-3 align-items-end">
            <div className="col-12 col-md-7"><label className="form-label small text-white-50">พิมพ์ข้อความแจ้งเตือน / สั่งการ</label><textarea className="form-control bg-dark text-white border-secondary" rows={2} placeholder="พิมพ์ข้อความที่นี่... (ระบบจะส่งเข้า LINE กลุ่มทันที)" value={msg} onChange={(e) => setMsg(e.target.value)} /></div>
            <div className="col-12 col-md-3"><label className="form-label small text-white-50">เป้าหมายสถานี</label>
              <select className="form-select bg-dark text-white border-secondary" value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="ALL">📢 แจ้งทุกสถานี (กก.{div})</option>
                {bs.map((s: any) => <option key={s.station} value={s.station}>เฉพาะ {s.name}</option>)}
              </select>
            </div>
            <div className="col-12 col-md-2"><button className="btn btn-info w-100 fw-bold h-100" onClick={sendOrder}><i className="fa-solid fa-paper-plane"></i> ถ่ายทอดคำสั่ง</button></div>
          </div>
        </div>

        {/* KPIs */}
        <div className="row g-3 mb-4">
          {kpis.map((k, i) => (
            <div className="col-md-2 col-6" key={i}><div className={`sc-kpi ${k.c}`}><div className="icon"><i className={`fa-solid ${k.i}`}></i></div><div className="value">{k.v ?? 0}</div><div className="title">{k.l}</div></div></div>
          ))}
        </div>

        {data && (
          <>
            <div className="row g-4 mb-4">
              <div className="col-12">
                <div className="glass-card"><h5 className="text-white mb-1"><i className="fa-solid fa-layer-group text-info"></i> ผลการปฏิบัติงานทั่วไปและจิตอาสา</h5><p className="small text-white-50 mb-3">เปรียบเทียบ ว.20 · บริการ · จิตอาสา แยกตามสถานี</p>
                  <ReactApexChart type="bar" height={320} options={vBarOptions(bs.map((s: any) => s.name), ['#ffc107', '#0dcaf0', '#20c997'])} series={[{ name: 'ว.20', data: bs.map((s: any) => s.v20) }, { name: 'บริการ', data: bs.map((s: any) => s.service) }, { name: 'จิตอาสา', data: bs.map((s: any) => s.volunteer) }]} />
                </div>
              </div>
            </div>
            <div className="row g-4 mb-4">
              <div className="col-12 col-lg-6"><div className="glass-card h-100"><h5 className="text-danger mb-1"><i className="fa-solid fa-handcuffs"></i> สถิติการจับกุมแยกตามสถานี</h5><p className="small text-white-50 mb-3">เปรียบเทียบผลงานการจับกุมของแต่ละสถานี</p><ReactApexChart type="bar" height={300} options={hBarOptions(bs.map((s: any) => s.name), '#ef4444')} series={[{ name: 'จับกุม', data: bs.map((s: any) => s.arrest) }]} /></div></div>
              <div className="col-12 col-lg-6"><div className="glass-card h-100"><h5 className="text-success mb-1"><i className="fa-solid fa-shield-halved text-warning"></i> ภารกิจรับเสด็จแยกตามสถานี</h5><p className="small text-white-50 mb-3">เปรียบเทียบจำนวนครั้งการปฏิบัติภารกิจรับเสด็จ</p><ReactApexChart type="bar" height={300} options={hBarOptions(bs.map((s: any) => s.name), '#20c997')} series={[{ name: 'รับเสด็จ', data: bs.map((s: any) => s.royalGuard) }]} /></div></div>
            </div>
            <div className="row g-4 mb-4">
              <div className="col-12 col-lg-6"><div className="glass-card h-100"><h5 className="text-warning mb-1"><i className="fa-solid fa-boxes-packing"></i> สถิติหมวดหมู่ของกลาง</h5><p className="small text-white-50 mb-3">สัดส่วนประเภทของกลางที่ตรวจยึดได้</p><ReactApexChart type="donut" height={320} options={donutOptions(Object.keys(data.seizedBreakdown))} series={Object.values(data.seizedBreakdown) as number[]} /></div></div>
              <div className="col-12 col-lg-6"><div className="glass-card h-100"><h5 className="text-info mb-1"><i className="fa-solid fa-gavel"></i> สัดส่วนข้อหา</h5><p className="small text-white-50 mb-3">ข้อหาที่พบบ่อยในกองกำกับการ</p><ReactApexChart type="donut" height={320} options={donutOptions(Object.keys(data.chargeBreakdown))} series={Object.values(data.chargeBreakdown) as number[]} /></div></div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
