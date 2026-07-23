import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import Swal from 'sweetalert2';

const VIEW_TITLES: Record<string, string> = {
  overview: 'ภาพรวมประจำวัน',
  pending: 'ผลปฏิบัติ / รายงาน (รอตรวจ)',
  fuel_approve: 'บันทึกเติมน้ำมัน (รอตรวจ)',
  mission_view: 'เรียกดูภารกิจหน่วย',
  fuel_stats: 'โควตาและการใช้น้ำมัน',
  daily_detail: 'แฟ้มข้อมูล / ส่งออก Excel',
  summary: 'สรุปยอดส่ง',
  manpower: 'ทำเนียบกำลังพลสถานี',
};

const stationName = (st?: string) => {
  const s = String(st || '').trim();
  const div = s.substring(0, 1);
  if (s.endsWith('0')) return 'กก.' + div;
  return 'ส.ทล.' + s.substring(1) + ' กก.' + div;
};

export const StationAdminDashboard: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user, logout } = useAuth();
  const [view, setView] = useState('overview');
  const [clock, setClock] = useState('--:--:--');
  const [data, setData] = useState<any | null>(null);

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString('th-TH')), 1000);
    return () => clearInterval(t);
  }, []);

  const load = async () => {
    const res = await api.getStationPending(user?.station || '', user?.token);
    if (res.status === 'success') setData(res.data);
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stats = data?.stats || {};
  const pending = data?.pending || [];
  const fuel = data?.fuel || [];

  const approve = async (sheetName: string, recordId: string) => {
    const r = await Swal.fire({ title: 'ยืนยันการอนุมัติรายงาน?', text: `อนุมัติ ${recordId} เข้าสู่ฐานข้อมูลหลัก`, icon: 'question', showCancelButton: true, confirmButtonText: 'อนุมัติ', cancelButtonText: 'ยกเลิก', confirmButtonColor: '#10b981' });
    if (!r.isConfirmed) return;
    await api.approveItem(sheetName, recordId, user?.token);
    setData((d: any) => ({ ...d, pending: d.pending.filter((x: any) => x.recordId !== recordId), fuel: d.fuel.filter((x: any) => x.recordId !== recordId) }));
    Swal.fire('สำเร็จ', 'อนุมัติรายการเรียบร้อยแล้ว', 'success');
  };
  const reject = async (sheetName: string, recordId: string) => {
    const r = await Swal.fire({ title: 'ระบุเหตุผลการตีกลับ/ยกเลิก', input: 'text', inputPlaceholder: 'กรอกเหตุผล...', showCancelButton: true, confirmButtonText: 'ส่งคืน', cancelButtonText: 'ยกเลิก', confirmButtonColor: '#ef4444' });
    if (!r.isConfirmed || !r.value) return;
    await api.cancelRecord(sheetName, recordId, user?.username || '', user?.token);
    setData((d: any) => ({ ...d, pending: d.pending.filter((x: any) => x.recordId !== recordId), fuel: d.fuel.filter((x: any) => x.recordId !== recordId) }));
    Swal.fire('ส่งคืนแล้ว', `ตีกลับรายการ ${recordId} เรียบร้อยแล้ว`, 'info');
  };

  const SidebarItem = ({ id, icon, label, cls = '', badge }: { id: string; icon: string; label: React.ReactNode; cls?: string; badge?: number }) => (
    <div className={`sidebar-item ${cls} ${view === id ? 'active' : ''}`} onClick={() => setView(id)}>
      <i className={`fa-solid ${icon}`}></i> {label}
      {badge ? <span className="badge bg-danger ms-auto rounded-pill">{badge}</span> : null}
    </div>
  );

  return (
    <div className="dashboard-wrapper hq-bg animate-fade-in">
      {/* Sidebar */}
      <div className="dash-sidebar">
        <div className="sidebar-header">
          <h4 className="text-info m-0">Admin Dashboard</h4>
          <small className="text-white-50">{stationName(user?.station)}</small>
        </div>
        <div className="sidebar-menu">
          <SidebarItem id="overview" icon="fa-chart-line" label="ภาพรวมประจำวัน" />
          <h6 className="text-white-50 px-4 mt-3 mb-2 small"><i className="fa-solid fa-bell"></i> รายการรอตรวจสอบ</h6>
          <SidebarItem id="pending" icon="fa-list-check" label="ผลปฏิบัติ / รายงาน" badge={pending.length} />
          <SidebarItem id="fuel_approve" icon="fa-gas-pump" label="บันทึกเติมน้ำมัน" badge={fuel.length} />
          <h6 className="text-white-50 px-4 mt-4 mb-2 small"><i className="fa-solid fa-folder-tree"></i> ข้อมูลส่วนสถานี</h6>
          <SidebarItem id="mission_view" icon="fa-list-check" label="เรียกดูภารกิจหน่วย" />
          <SidebarItem id="fuel_stats" icon="fa-oil-can" label="โควตาและการใช้น้ำมัน" cls="text-warning" />
          <SidebarItem id="daily_detail" icon="fa-folder-open" label="แฟ้มข้อมูล / ส่งออก Excel" cls="text-success" />
          <SidebarItem id="summary" icon="fa-paper-plane" label={<>สรุปยอดส่ง {stationName(user?.station)}</>} cls="text-info" />
          <SidebarItem id="manpower" icon="fa-sitemap" label="ทำเนียบกำลังพลสถานี" cls="text-primary" />
        </div>
        <div className="mt-auto border-top border-secondary p-3">
          <div className="sidebar-item text-warning" onClick={onBack}><i className="fa-solid fa-rotate"></i> กลับโหมดผู้ปฏิบัติ</div>
          <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
        </div>
      </div>

      {/* Main */}
      <div className="main-content">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h3 className="m-0 text-white">{VIEW_TITLES[view]}</h3>
            <p className="text-white-50 small m-0">ยินดีต้อนรับ, <span className="text-info">{user?.fullName}</span></p>
          </div>
          <div className="text-info" style={{ fontSize: '1.2rem', fontWeight: 600 }}>{clock}</div>
        </div>

        {/* OVERVIEW */}
        {view === 'overview' && (
          <>
            <div className="row g-3">
              <div className="col-md-4 col-6"><div className="kpi-card" style={{ background: 'rgba(13, 202, 240, 0.1)', borderColor: '#0dcaf0' }} onClick={() => setView('pending')}><div className="title">ผลปฏิบัติรอตรวจ</div><div className="value text-info">{stats.pendingCount ?? 0}</div></div></div>
              <div className="col-md-4 col-6"><div className="kpi-card" style={{ background: 'rgba(220, 53, 69, 0.1)', borderColor: '#dc3545' }} onClick={() => setView('fuel_approve')}><div className="title">รายการน้ำมันรอตรวจ</div><div className="value text-danger">{stats.fuelCount ?? 0}</div></div></div>
              <div className="col-md-4 col-6"><div className="kpi-card" style={{ background: 'rgba(25, 135, 84, 0.1)', borderColor: '#198754' }}><div className="title">อนุมัติแล้ววันนี้</div><div className="value text-success">{stats.approvedToday ?? 0}</div></div></div>
            </div>

            <div className="mt-4 p-4 glass-card w-100">
              <h5 className="text-white mb-3"><i className="fa-solid fa-crown text-warning"></i> สรุปผลการปฏิบัติภาพรวมสถานี</h5>
              <div className="row g-3 mb-3">
                {[
                  { t: 'รวม ว.43', i: 'fa-road', c: 'text-primary', bg: 'rgba(13, 110, 253, 0.1)', bd: '#0d6efd', v: stats.v43 },
                  { t: 'รวม ว.42', i: 'fa-car-side', c: 'text-secondary', bg: 'rgba(108, 117, 125, 0.1)', bd: '#6c757d', v: stats.v42 },
                  { t: 'รวม ว.20', i: 'fa-file-invoice', c: 'text-warning', bg: 'rgba(255, 193, 7, 0.1)', bd: '#ffc107', v: stats.v20 },
                  { t: 'รายงานจับกุม', i: 'fa-handcuffs', c: 'text-danger', bg: 'rgba(220, 53, 69, 0.1)', bd: '#dc3545', v: stats.arrest },
                  { t: 'รวม จิตอาสา', i: 'fa-hands-holding-child', c: 'text-info', bg: 'rgba(13, 202, 240, 0.1)', bd: '#0dcaf0', v: stats.volunteer },
                  { t: 'รวม รับเสด็จ', i: 'fa-shield-halved', c: 'text-success', bg: 'rgba(25, 135, 84, 0.1)', bd: '#198754', v: stats.royalGuard },
                ].map((k, i) => (
                  <div className="col-md-2 col-6" key={i}><div className="kpi-card" style={{ background: k.bg, borderColor: k.bd }}><div className="title"><i className={`fa-solid ${k.i}`}></i> {k.t}</div><div className={`value ${k.c}`}>{k.v ?? '-'}</div></div></div>
                ))}
              </div>
              <div className="table-responsive">
                <table className="table table-hq table-bordered text-center align-middle">
                  <thead><tr><th className="text-start">ประเภทการปฏิบัติ</th><th className="text-white-50">หน่วยดอนจาน</th><th className="text-white-50">หน่วยจอมทอง</th><th className="text-warning">รวมทั้งสถานี</th></tr></thead>
                  <tbody>
                    {[['ว.43', 88, 60, stats.v43], ['ว.20', 18, 13, stats.v20], ['จับกุม', 7, 5, stats.arrest]].map((r, i) => (
                      <tr key={i}><td className="text-start">{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td className="text-warning fw-bold">{r[3] ?? '-'}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* PENDING */}
        {view === 'pending' && (
          <div className="glass-card w-100 p-4">
            <div className="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-3">
              <h5 className="text-info m-0"><i className="fa-solid fa-list-check"></i> ผลการปฏิบัติ/จับกุม/อุบัติเหตุ/รับเสด็จ</h5>
              <button className="btn btn-sm btn-outline-info" onClick={load}><i className="fa-solid fa-rotate"></i> รีเฟรช</button>
            </div>
            <div className="table-responsive">
              <table className="table table-hq align-middle text-center">
                <thead><tr><th className="text-start">เวลาส่งรายงาน</th><th className="text-start">หมวดหมู่</th><th className="text-start">หน่วย / ผู้รายงาน</th><th className="text-center">ตรวจสอบ</th></tr></thead>
                <tbody>
                  {pending.length === 0 && <tr><td colSpan={4} className="text-center py-4 text-success"><i className="fa-solid fa-check-circle fs-3"></i><br />ไม่มีรายการค้างตรวจอนุมัติ</td></tr>}
                  {pending.map((it: any) => (
                    <tr key={it.recordId}>
                      <td className="text-start small text-white-50">{it.timestamp}</td>
                      <td className="text-start"><div className="fw-bold text-white"><i className={`fa-solid ${it.icon} text-info`}></i> {it.formType}</div><small className="text-secondary">{it.details}</small></td>
                      <td className="text-start">{it.reporter}<br /><small className="text-white-50">{it.unit}</small></td>
                      <td className="text-center">
                        <div className="d-flex gap-2 justify-content-center">
                          <button className="btn btn-sm btn-outline-success" onClick={() => approve(it.sheetName, it.recordId)}><i className="fa-solid fa-check"></i> อนุมัติ</button>
                          <button className="btn btn-sm btn-outline-danger" onClick={() => reject(it.sheetName, it.recordId)}><i className="fa-solid fa-xmark"></i> ตีกลับ</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* FUEL APPROVE */}
        {view === 'fuel_approve' && (
          <div className="glass-card w-100 p-4">
            <div className="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-3">
              <h5 className="text-danger m-0"><i className="fa-solid fa-gas-pump"></i> คำร้องบันทึกเติมน้ำมันรถยนต์</h5>
              <button className="btn btn-sm btn-outline-danger" onClick={load}><i className="fa-solid fa-rotate"></i> รีเฟรช</button>
            </div>
            <div className="table-responsive">
              <table className="table table-hq align-middle text-center">
                <thead><tr><th className="text-start">วันที่เติม</th><th className="text-start">รถวิทยุ</th><th className="text-start">รายละเอียด</th><th className="text-center">ตรวจสอบ</th></tr></thead>
                <tbody>
                  {fuel.length === 0 && <tr><td colSpan={4} className="text-center py-4 text-success">ไม่มีคำร้องน้ำมันค้างตรวจ</td></tr>}
                  {fuel.map((it: any) => (
                    <tr key={it.recordId}>
                      <td className="text-start small text-white-50">{it.timestamp}</td>
                      <td className="text-start">{it.plate}</td>
                      <td className="text-start">{it.details}</td>
                      <td className="text-center"><div className="d-flex gap-2 justify-content-center"><button className="btn btn-sm btn-outline-success" onClick={() => approve(it.sheetName, it.recordId)}><i className="fa-solid fa-check"></i> อนุมัติ</button><button className="btn btn-sm btn-outline-danger" onClick={() => reject(it.sheetName, it.recordId)}><i className="fa-solid fa-xmark"></i></button></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Other views — faithful section shell, data pending backend */}
        {['mission_view', 'fuel_stats', 'daily_detail', 'summary', 'manpower'].includes(view) && (
          <div className="glass-card w-100 p-4 text-center py-5">
            <i className="fa-solid fa-database text-info mb-3" style={{ fontSize: '2.5rem' }}></i>
            <h5 className="text-white">{VIEW_TITLES[view]}</h5>
            <p className="text-white-50 mb-0">ส่วนนี้พร้อมแสดงผลเมื่อเชื่อมต่อกับ Backend (FastAPI) — โครงหน้าตรงตามต้นฉบับแล้ว</p>
          </div>
        )}
      </div>
    </div>
  );
};
