import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getNowDateLocal } from '../../utils/formHelpers';
import { ReactApexChart, hBarOptions, vBarOptions, donutOptions } from './chartHelpers';
import { DashboardLayout } from './DashboardLayout';
import { recentStart } from './hq/panelHelpers';
import { DeepSearchModal } from './DeepSearchModal';
import { MissionCalendar } from './hq/MissionCalendar';
import { EvidencePanel } from './hq/EvidencePanel';
import { EscortPanel } from './hq/EscortPanel';
import { MapPanelLazy } from './hq/MapPanelLazy';
import { TextSummaryModal } from './hq/TextSummaryModal';
import { captureToImage } from './hq/captureImage';
import Swal from 'sweetalert2';


interface Props {
  onBack: () => void;
  onSwitchHQ?: () => void;
  /** ดูหน่วยอื่นแทนหน่วยตัวเอง — ผบก. ใช้เจาะลึกลง กก. ที่เลือก */
  viewStation?: string;
  viewLabel?: string;
  onExitView?: () => void;
  onViewStation?: (stationId: string, label: string) => void;
}

export const CommanderDashboard: React.FC<Props> = ({ onBack, onSwitchHQ, viewStation, viewLabel, onExitView, onViewStation }) => {
  const { user, logout } = useAuth();
  // ของเดิมสลับ userData.station ใน localStorage ชั่วคราวแล้วโหลดใหม่ ที่นี่ส่งเป็น prop
  // แทน ได้ผลเหมือนกันแต่ไม่ต้องเขียนทับตัวตนของคนที่ล็อกอินอยู่
  // requirement ข้อ 1 — ผกก. เลือกดูสถิติของ กก. อื่นได้ แต่สั่งการได้เฉพาะกองตัวเอง
  // `viewDivision` ว่าง = ดูกองตัวเอง ค่าอื่นคือสถานี ฝอ. ของกองที่เลือก เช่น "10"
  const [divisions, setDivisions] = useState<{ division: string; name: string; station: string; isOwn: boolean }[]>([]);
  const [viewDivision, setViewDivision] = useState('');

  // ลำดับความสำคัญ: ผบก. เจาะลงมา > ผกก. เลือกดูกองอื่น > กองของตัวเอง
  const station = viewStation || viewDivision || user?.station || '';
  const ownStation = user?.station || '';
  const div = String(station || '5').charAt(0);
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(getNowDateLocal());
  const [data, setData] = useState<any | null>(null);
  const [exec, setExec] = useState<any | null>(null);
  const [msg, setMsg] = useState('');
  const [target, setTarget] = useState('ALL');
  const [sending, setSending] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [view, setView] = useState<'overview' | 'evidence' | 'escort' | 'map'>('overview');
  const [summaryOpen, setSummaryOpen] = useState(false);
  // กราฟนำขบวนกับโดนัทกำลังพลของเดิมอ่านจากสองชุดนี้ ดึงมาพร้อมภาพรวมในรอบเดียว
  const [escort, setEscort] = useState<any | null>(null);

  const load = async () => {
    // ยิงคู่กัน หน้านี้เปิดครั้งเดียวแล้วดูยาว การรอทีละคำขอทำให้ช้าขึ้นเปล่า ๆ
    //
    // เคยยิงสามตัวโดยมี division-summary แยกอีกคำขอ ทั้งที่ commander/overview
    // คำนวณสรุปก้อนเดียวกันอยู่แล้ว ตอนนี้เอามาจาก overview.summary แทน เพราะทุกคำขอ
    // ที่อ่านชีตพร้อมกันไปกินโควตา 60 ครั้ง/นาทีของ Google ซึ่งคิดรวมทั้งระบบ
    const [overview, escortRes] = await Promise.all([
      api.commanderOverview(station, start, end, user?.token),
      api.hqEscort(station, start, end, user?.token),
    ]);
    const summary = overview.status === 'success'
      ? { status: 'success', data: overview.data.summary }
      : overview;
    // โหลดล้มต้องบอกให้รู้ ไม่ใช่ปล่อยให้ KPI ขึ้น 0 ซึ่งอ่านว่า "ไม่มีผลงาน" — ผู้บังคับ
    // บัญชีแยกไม่ออกว่าเป็นเพราะไม่มีข้อมูลจริงหรือเรียกข้อมูลไม่สำเร็จ
    if (summary.status === 'success') { setData(summary.data); setLoadError(''); }
    else setLoadError(summary.message || 'โหลดข้อมูลไม่สำเร็จ');
    if (overview.status === 'success') setExec(overview.data);
    if (escortRes.status === 'success') setEscort(escortRes.data);
  };
  // โหลดใหม่เมื่อสลับไปดู กก. อื่น ไม่งั้นหัวเปลี่ยนแต่ตัวเลขยังเป็นของหน่วยเดิม
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

  // รายชื่อ กก. ที่เปิดดูได้ ไม่โหลดตอน ผบก. เจาะลงมาเพราะหน้านั้นมีตัวเลือกของตัวเองอยู่แล้ว
  useEffect(() => {
    if (viewStation) return;
    api.commanderDivisions(user?.token).then((res) => {
      if (res.status === 'success') setDivisions(res.data || []);
    });
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  // ธงจาก API ไม่ใช่คำนวณเองฝั่งหน้าเว็บ จะได้ตรงกับที่ backend ตัดสินจริงเสมอ
  // ระหว่างที่ยังโหลดไม่เสร็จ ใช้การเทียบเลข กก. ไปก่อนเพื่อไม่ให้กล่องสั่งการแวบขึ้นมา
  const readOnly = exec?.readOnly ?? (Boolean(ownStation) && ownStation[0] !== String(station)[0]);

  // ค่าตั้งต้นกันหน้าขาวทั้งหน้าเมื่อ API ไม่ส่งฟิลด์นี้มา (เช่นข้อมูลชุดเก่าหรือ
  // ตอนที่รวมยอดยังไม่เสร็จ) ของเดิมอ่านตรง ๆ แล้ว Object.keys(undefined) ทำให้
  // ทั้งแดชบอร์ดล่ม ซึ่งอ่านเหมือนระบบพังทั้งระบบทั้งที่ขาดแค่กราฟใบเดียว
  const seized = data?.seizedBreakdown || {};

  const t = data?.totals || {};
  const bs = data?.byStation || [];

  // ต้นฉบับนับนำขบวนรายสถานีจากรายการดิบ เพราะ summary บอกแค่ยอดรวมทั้งกอง ไม่บอกว่า
  // สถานีไหนรับภาระหนัก ซึ่งเป็นสิ่งที่กราฟแท่งซ้อนกับบรรทัด "สถานีที่รับภาระสูงสุด" ใช้
  const escortByStation = bs.map((s: any) => {
    const bucket = { name: s.name, vip: 0, gen: 0 };
    (escort?.records || []).forEach((r: any) => {
      // ฝั่งนำขบวนส่งชื่อเต็มมาแบบ "ส.ทล.1 (สระบุรี)" ส่วนแกนกราฟใช้ชื่อสั้น ตัดวงเล็บทิ้งก่อนเทียบ
      if (String(r.station || '').split('(')[0].trim() !== s.name) return;
      if (String(r.type || '').includes('สำคัญ')) bucket.vip++;
      else bucket.gen++;
    });
    return bucket;
  });
  const escortTop = escortByStation.reduce(
    (best: any, cur: any) => (cur.vip + cur.gen > best.vip + best.gen ? cur : best),
    { name: '', vip: 0, gen: 0 },
  );

  /** แคปหน้า Dashboard ทั้งหน้าเป็นรูปเดียว ส่งเข้า LINE ได้ทันที */
  const saveAsImage = () => {
    const content = document.querySelector('.main-content') as HTMLElement | null;
    if (!content) return;
    captureToImage({
      target: content,
      filename: `HWPD_กก${div}_Executive_Report_${new Date().toISOString().split('T')[0]}`,
      hide: [content.querySelector('.btn-outline-warning.d-md-none') as HTMLElement | null],
    });
  };

  const sendOrder = async () => {
    if (!msg.trim()) return Swal.fire('แจ้งเตือน', 'กรุณาพิมพ์ข้อความก่อน', 'warning');

    // คำสั่งเข้ากลุ่ม LINE ของทุกสถานีทันทีและถอนคืนไม่ได้ จึงถามยืนยันก่อนเสมอ
    const scope = target === 'ALL' ? `ทุกสถานีใน กก.${div}` : bs.find((s: any) => s.station === target)?.name || target;
    const confirm = await Swal.fire({
      title: 'ยืนยันการสั่งการ',
      html: `ข้อความจะถูกส่งเข้ากลุ่ม LINE ของ <b>${scope}</b> ทันที และเรียกคืนไม่ได้`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'ส่งคำสั่ง',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#0dcaf0',
    });
    if (!confirm.isConfirmed) return;

    setSending(true);
    const res = await api.commanderOrder({ target, message: msg, commanderName: user?.fullName }, user?.token);
    setSending(false);
    if (res.status === 'success') {
      setMsg('');
      // requirement ข้อ 2 — โชว์เบอร์หัวหน้าหน่วยที่ได้รับคำสั่ง ให้โทรตามได้ทันที
      // โดยไม่ต้องเปิดทำเนียบกำลังพลอีกหน้า
      const contacts: any[] = res.contacts || [];
      const rows = contacts
        .map((c) => {
          const heads = (c.heads || [])
            .map((h: any) => `${h.name}${h.phone ? ` <a href="tel:${h.phone}">${h.phone}</a>` : ' (ไม่มีเบอร์ในระบบ)'}`)
            .join('<br>');
          return `<div style="margin-bottom:.6rem"><b>${c.stationName}</b><br>${heads || '<span style="color:#dc3545">ยังไม่มีข้อมูลหัวหน้าหน่วยในระบบ</span>'}</div>`;
        })
        .join('');
      await Swal.fire({
        icon: 'success',
        title: 'ส่งคำสั่งแล้ว',
        html: `<p>${res.message || ''}</p>${rows ? `<hr><div style="text-align:left"><b>ผู้รับคำสั่งที่ติดต่อได้</b><br>${rows}</div>` : ''}`,
        confirmButtonColor: '#0dcaf0',
      });
    } else {
      Swal.fire('ส่งไม่สำเร็จ', res.message || '', 'error');
    }
  };

  // ห้าใบ เรียงตามที่ renderCommanderKPIs ของต้นฉบับสร้าง ใบสุดท้ายคือกำลังพลที่
  // ปฏิบัติงานจริง ไม่ใช่ยอดผลงาน — ผู้กำกับการต้องเห็นคู่กันว่างานเท่านี้ทำด้วยคนเท่าไหร่
  const kpis = [
    { c: 'text-info', i: 'fa-file-invoice', v: t.v20, l: 'รวม ว.20' },
    { c: 'text-danger', i: 'fa-handcuffs', v: t.arrest, l: 'ยอดจับกุม' },
    { c: 'text-success', i: 'fa-shield-halved', v: t.royalGuard, l: 'รับเสด็จ' },
    { c: 'text-primary', i: 'fa-hands-holding-child', v: t.volunteer, l: 'จิตอาสา' },
    { c: 'text-warning', i: 'fa-users', v: exec?.manpower?.total?.net, l: 'ปฏิบัติงานจริง' },
  ];

  return (
    <DashboardLayout
      variant="sc"
      bg="sc-bg"
      sidebar={(close) => (
        <>
          <div className="sidebar-header">
            <h4 className="text-warning m-0" style={{ textShadow: '0 0 10px rgba(250,204,21,0.5)' }}><i className="fa-solid fa-star"></i> ผู้กำกับการ</h4>
            <small className="text-white-50">Executive Command · กก.{div}</small>
          </div>
          <div className="sidebar-menu">
            <div className={`sidebar-item ${view === 'overview' ? 'active' : ''}`} onClick={() => { close(); setView('overview'); }}><i className="fa-solid fa-chart-line"></i> ภาพรวมระดับบริหาร (Executive)</div>
            <div className={`sidebar-item ${view === 'evidence' ? 'active' : ''}`} onClick={() => { close(); setView('evidence'); }}><i className="fa-solid fa-boxes-packing"></i> ของกลางที่ตรวจยึด</div>
            <div className={`sidebar-item ${view === 'escort' ? 'active' : ''}`} onClick={() => { close(); setView('escort'); }}><i className="fa-solid fa-motorcycle"></i> งานนำขบวน</div>
            <div className={`sidebar-item ${view === 'map' ? 'active' : ''}`} onClick={() => { close(); setView('map'); }}><i className="fa-solid fa-map-location-dot"></i> แผนที่ผลการปฏิบัติ</div>
            <h6 className="text-white-50 px-4 mt-4 mb-2 small"><i className="fa-solid fa-sitemap"></i> ทางลัดการเข้าถึงระบบ</h6>
            {onSwitchHQ && <div className="sidebar-item text-info" onClick={() => { close(); onSwitchHQ(); }}><i className="fa-solid fa-building-shield"></i> เข้าสู่หน้า ฝอ. (HQ Dashboard)</div>}
            <div className="px-4 mt-3 mb-2 small text-warning">เจาะลึกรายสถานี:</div>
            {bs.map((s: any) => (
              <div className="sidebar-item text-secondary py-1" key={s.station}
                   onClick={() => { close(); onViewStation?.(String(s.station), s.name); }}> {s.name}</div>
            ))}
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            {/* ของเดิมโชว์ปุ่มนี้ (cmdBackToScBtn) เฉพาะตอนถูกเรียกจากหน้า ผบก. */}
            {viewStation && onExitView && (
              <div className="sidebar-item text-warning" onClick={() => { close(); onExitView(); }}>
                <i className="fa-solid fa-arrow-left"></i> กลับหน้าผู้บังคับการ
              </div>
            )}
            <div className="sidebar-item text-danger" onClick={logout}><i className="fa-solid fa-power-off"></i> ออกจากระบบ</div>
          </div>
        </>
      )}
    >
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
          <div className="d-flex align-items-center gap-3">
            <button className="btn btn-outline-warning btn-sm" onClick={onBack}><i className="fa-solid fa-arrow-left"></i></button>
            <div><h3 className="text-white m-0">Executive Dashboard</h3><p className="text-white-50 small m-0 mt-1">ยินดีต้อนรับ, <span className="text-warning">{user?.fullName}</span>{viewStation && <span className="text-info"> (มุมมอง {viewLabel || 'กก.' + div})</span>}</p></div>
          </div>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <input type="date" className="form-control form-control-sm bg-dark text-white border-warning" style={{ width: 150 }} value={start} onChange={(e) => setStart(e.target.value)} />
            <span className="text-white-50 fw-bold">-</span>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-warning" style={{ width: 150 }} value={end} onChange={(e) => setEnd(e.target.value)} />
            <button className="btn btn-warning fw-bold px-3" onClick={load}><i className="fa-solid fa-rotate"></i></button>
            <button className="btn btn-outline-light fw-bold px-3" onClick={saveAsImage} title="บันทึกหน้านี้เป็นรูปภาพ">
              <i className="fa-solid fa-image"></i>
            </button>
            <button className="btn btn-success fw-bold px-3" onClick={() => setSummaryOpen(true)}>
              <i className="fa-solid fa-file-lines"></i> Export สรุปรายงาน
            </button>
            <button className="btn btn-info fw-bold px-3" onClick={() => setSearchOpen(true)}><i className="fa-solid fa-user-secret"></i> แกะรอยผลงาน</button>
          </div>
        </div>

        {view === 'evidence' && <EvidencePanel station={station} canEdit={false} />}
        {view === 'escort' && <EscortPanel station={station} canEdit={false} />}
        {view === 'map' && (
          <MapPanelLazy station={station} stations={bs.map((s: any) => ({ station: String(s.station), name: s.name }))} />
        )}

        {view === 'overview' && (<>
        {/* เลือก กก. ที่จะดูสถิติ (requirement ข้อ 1) ไม่โชว์ตอน ผบก. เจาะลงมา
            เพราะหน้านั้นมีทางกลับของตัวเองอยู่แล้ว */}
        {!viewStation && divisions.length > 1 && (
          <div className="cmd-card mb-4" style={{ borderColor: 'rgba(250,204,21,0.35)' }}>
            <div className="d-flex flex-wrap align-items-center gap-2">
              <span className="small text-white-50"><i className="fa-solid fa-sitemap"></i> ดูสถิติของกองกำกับการ</span>
              {divisions.map((d) => (
                <button
                  key={d.division}
                  type="button"
                  className={`btn btn-sm ${station === d.station ? 'btn-warning fw-bold' : 'btn-outline-warning'}`}
                  onClick={() => setViewDivision(d.isOwn ? '' : d.station)}
                >
                  {d.name}{d.isOwn ? ' (ของท่าน)' : ''}
                </button>
              ))}
              {readOnly && (
                <span className="badge bg-warning text-dark ms-auto">
                  <i className="fa-solid fa-eye"></i> โหมดดูอย่างเดียว — สั่งการหน่วยนี้ไม่ได้
                </span>
              )}
            </div>
          </div>
        )}

        {/* Command Center — ซ่อนตอนดูกองอื่น การโชว์ปุ่มที่กดแล้วได้ 403 คือพาไปเจอ error */}
        {!readOnly && (
        <div className="cmd-card mb-4" style={{ borderColor: 'rgba(13,202,240,0.4)' }}>
          <h5 className="text-info mb-3"><i className="fa-solid fa-walkie-talkie"></i> ศูนย์สั่งการผู้บังคับบัญชา (Command Center)</h5>
          <div className="row g-3 align-items-end">
            <div className="col-12 col-md-7"><label className="form-label small text-white-50">พิมพ์ข้อความแจ้งเตือน / สั่งการ</label><textarea className="form-control bg-dark text-white border-secondary" rows={2} placeholder="พิมพ์ข้อความที่นี่... (ระบบจะส่งเข้า LINE กลุ่มทันที)" value={msg} onChange={(e) => setMsg(e.target.value)} /></div>
            <div className="col-12 col-md-3"><label className="form-label small text-white-50">เป้าหมายสถานี</label>
              <select className="form-select bg-dark text-white border-secondary" value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="ALL">📢 แจ้งทุกสถานี (กก.{div})</option>
                {bs.map((s: any) => <option key={s.station} value={s.station}>เฉพาะ {s.name}</option>)}
              </select>
            </div>
            <div className="col-12 col-md-2"><button className="btn btn-info w-100 fw-bold h-100" onClick={sendOrder} disabled={sending}><i className="fa-solid fa-paper-plane"></i> {sending ? 'กำลังส่ง...' : 'ถ่ายทอดคำสั่ง'}</button></div>
          </div>
        </div>
        )}

        {loadError && (
          <div className="alert alert-danger d-flex justify-content-between align-items-center py-2 mb-4">
            <span><i className="fa-solid fa-triangle-exclamation"></i> {loadError} — ตัวเลขด้านล่างยังไม่ใช่ข้อมูลจริง</span>
            <button className="btn btn-sm btn-outline-light" onClick={load}>ลองใหม่</button>
          </div>
        )}

        {/* KPIs */}
        <div className="row g-3 mb-4">
          {kpis.map((k, i) => (
            <div className="col-md col-6" key={i}><div className={`cmd-kpi ${k.c}`}><div className="icon"><i className={`fa-solid ${k.i}`}></i></div><div className="value">{k.v ?? 0}</div><div className="title">{k.l}</div></div></div>
          ))}
        </div>

        {data && (
          <>
            <div className="row g-4 mb-4">
              <div className="col-12">
                <div className="cmd-card"><h5 className="text-white mb-1"><i className="fa-solid fa-layer-group text-info"></i> ผลการปฏิบัติงานทั่วไปและจิตอาสา</h5><p className="small text-white-50 mb-3">เปรียบเทียบ ว.20 · ว.42 · จิตอาสา แยกตามสถานี</p>
                  <ReactApexChart type="bar" height={320}
                    options={{ ...vBarOptions(bs.map((s: any) => s.name), ['#ffc107', '#6c757d', '#0dcaf0']),
                               chart: { type: 'bar', height: 320, stacked: true, toolbar: { show: false }, background: 'transparent' } }}
                    series={[{ name: 'ว.20', data: bs.map((s: any) => s.v20) }, { name: 'ว.42', data: bs.map((s: any) => s.v42) }, { name: 'จิตอาสา', data: bs.map((s: any) => s.volunteer) }]} />
                </div>
              </div>
            </div>
            <div className="row g-4 mb-4">
              <div className="col-12 col-lg-6"><div className="cmd-card h-100"><h5 className="text-danger mb-1"><i className="fa-solid fa-handcuffs"></i> สถิติการจับกุมแยกตามสถานี</h5><p className="small text-white-50 mb-3">เปรียบเทียบผลงานการจับกุมคดีอาญาของแต่ละสถานี</p><ReactApexChart type="bar" height={300} options={hBarOptions(bs.map((s: any) => s.name), '#ef4444')} series={[{ name: 'คดีอาญา', data: bs.map((s: any) => s.arrest) }]} /></div></div>
              <div className="col-12 col-lg-6"><div className="cmd-card h-100"><h5 className="text-success mb-1"><i className="fa-solid fa-shield-halved text-warning"></i> ภารกิจรับเสด็จแยกตามสถานี</h5><p className="small text-white-50 mb-3">เปรียบเทียบจำนวนครั้งการปฏิบัติภารกิจรับเสด็จ</p><ReactApexChart type="bar" height={300} options={hBarOptions(bs.map((s: any) => s.name), '#20c997')} series={[{ name: 'รับเสด็จ', data: bs.map((s: any) => s.royalGuard) }]} /></div></div>
            </div>
            <div className="row g-4 mb-4">
              <div className="col-12 col-lg-6">
                <div className="cmd-card h-100">
                  <h5 className="text-warning mb-1"><i className="fa-solid fa-boxes-packing"></i> สถิติหมวดหมู่ของกลาง</h5>
                  <p className="small text-white-50 mb-3">สัดส่วนประเภทของกลางที่ทำการตรวจยึดได้เข้าคลังข้อมูล</p>
                  <div className="row align-items-center">
                    <div className="col-12 col-md-7">
                      <ReactApexChart type="donut" height={280}
                        options={donutOptions(Object.keys(seized))}
                        series={Object.values(seized) as number[]} />
                    </div>
                    <div className="col-12 col-md-5">
                      {/* ต้นฉบับวางรายการสรุปไว้ข้างกราฟ เพราะโดนัทบอกสัดส่วนแต่ไม่บอกจำนวนจริง */}
                      <div className="p-3 rounded border border-secondary h-100" style={{ background: 'rgba(255,255,255,0.02)' }}>
                        <h6 className="text-warning border-bottom border-secondary pb-2 mb-2">
                          <i className="fa-solid fa-list-ul"></i> สรุปยอดของกลาง
                        </h6>
                        <ul className="list-unstyled mb-0 small" style={{ maxHeight: 220, overflowY: 'auto' }}>
                          {Object.entries(seized).length ? (
                            Object.entries(seized).map(([name, qty]) => (
                              <li key={name} className="d-flex justify-content-between border-bottom border-secondary py-1">
                                <span className="text-white-50 text-truncate" title={name}>{name}</span>
                                <span className="text-white fw-bold ms-2">{String(qty)}</span>
                              </li>
                            ))
                          ) : (
                            <li className="text-white-50 py-2">ไม่มีของกลางที่จัดหมวดหมู่แล้วในช่วงนี้</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="col-12 col-lg-6">
                <div className="cmd-card h-100">
                  <h5 className="text-info mb-1"><i className="fa-solid fa-motorcycle"></i> สถิติภารกิจนำขบวน</h5>
                  <p className="small text-white-50 mb-3">เปรียบเทียบภาระงานนำขบวนแยกระดับสถานี (VIP และ ทั่วไป)</p>
                  {escort?.summary?.total ? (
                    <div className="row align-items-center">
                      <div className="col-12 col-md-7">
                        <ReactApexChart type="bar" height={260}
                          options={{ ...vBarOptions(escortByStation.map((s: any) => s.name), ['#ef4444', '#10b981']),
                                     chart: { type: 'bar', height: 260, stacked: true, toolbar: { show: false }, background: 'transparent' },
                                     plotOptions: { bar: { borderRadius: 2, columnWidth: '50%' } },
                                     legend: { position: 'bottom', labels: { colors: '#8b949e' } } }}
                          series={[
                            { name: 'บุคคลสำคัญ', data: escortByStation.map((s: any) => s.vip) },
                            { name: 'ทั่วไป', data: escortByStation.map((s: any) => s.gen) },
                          ]} />
                      </div>
                      <div className="col-12 col-md-5">
                        {/* ต้นฉบับวางสรุปยอดไว้ข้างกราฟ เพราะกราฟบอกการกระจายรายสถานีแต่ไม่บอกยอดรวม */}
                        <div className="p-3 rounded border border-secondary h-100" style={{ background: 'rgba(255,255,255,0.02)' }}>
                          <h6 className="text-info border-bottom border-secondary pb-2 mb-3">
                            <i className="fa-solid fa-list-ul"></i> สรุปยอดนำขบวน
                          </h6>
                          <ul className="list-unstyled mb-0 small">
                            <li className="d-flex justify-content-between mb-2 pb-1 border-bottom border-secondary">
                              <span className="text-white-50">รวมภารกิจทั้งหมด:</span>
                              <span className="text-info fw-bold fs-5">{escort.summary.total} ครั้ง</span>
                            </li>
                            <li className="d-flex justify-content-between mb-2">
                              <span className="text-danger"><i className="fa-solid fa-star"></i> นำขบวน VIP:</span>
                              <span className="text-white">{escort.summary.vip} ครั้ง</span>
                            </li>
                            <li className="d-flex justify-content-between mb-3 border-bottom border-secondary pb-2">
                              <span className="text-success"><i className="fa-solid fa-motorcycle"></i> นำขบวนทั่วไป:</span>
                              <span className="text-white">{escort.summary.general} ครั้ง</span>
                            </li>
                            {escortTop.vip + escortTop.gen > 0 && (
                              <li className="d-flex justify-content-between mt-2 pt-1">
                                <span className="text-info small">สถานีที่รับภาระสูงสุด:</span>
                                <span className="text-warning fw-bold">{escortTop.name} ({escortTop.vip + escortTop.gen})</span>
                              </li>
                            )}
                          </ul>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-white-50 small mb-0 py-4 text-center">ไม่มีภารกิจนำขบวนในช่วงวันที่ที่เลือก</p>
                  )}
                </div>
              </div>
            </div>

            {/* แถวของตัวเองแบบเต็มความกว้าง ตามที่ต้นฉบับแยกไว้เป็น "แถวที่ 3.5" */}
            <div className="row g-4 mb-4">
              <div className="col-12">
                <div className="cmd-card h-100">
                  <h5 className="text-white mb-1">สถานภาพกำลังพล กก.{div}</h5>
                  <p className="small text-white-50 mb-3">สัดส่วนกำลังพลภาพรวมทั้งกองกำกับการ และแยกตามสถานี</p>
                  {exec?.manpower?.total ? (
                    <div className="row align-items-center">
                      <div className="col-12 col-lg-4">
                        <ReactApexChart type="donut" height={300}
                          options={donutOptions(['อยู่ปฏิบัติจริง', 'ไปช่วยราชการ', 'มาช่วยราชการ'], ['#0dcaf0', '#ef4444', '#20c997'])}
                          series={[
                            Math.max(0, exec.manpower.total.base - exec.manpower.total.out),
                            exec.manpower.total.out,
                            exec.manpower.total.in,
                          ]} />
                      </div>
                      {/*
                        ต้นฉบับวางการ์ดรายสถานีไว้ข้างโดนัท (manpowerStationList) เพราะโดนัท
                        บอกภาพรวมทั้งกองแต่ไม่บอกว่าสถานีไหนขาดคน ซึ่งเป็นสิ่งที่ผู้กำกับการ
                        ต้องเห็นเพื่อสั่งเกลี่ยกำลัง
                      */}
                      <div className="col-12 col-lg-8">
                        <div className="row g-3">
                          {Object.entries(exec.manpower)
                            .filter(([id]) => id !== 'total')
                            .map(([id, m]: [string, any]) => (
                              <div className="col-lg-3 col-md-4 col-6" key={id}>
                                <div className="p-2 rounded h-100"
                                     style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                                  <div className="text-white small text-truncate" title={m.name}>{m.name}</div>
                                  <div className="text-info fw-bold" style={{ fontSize: '1.4rem' }}>{m.net}</div>
                                  <div className="text-white-50" style={{ fontSize: '.72rem' }}>
                                    อัตรา {m.base} · ไป <span className="text-danger">{m.out}</span> · มา <span className="text-success">{m.in}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-white-50 small mb-0 py-4 text-center">ยังไม่มีข้อมูลกำลังพล</p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        <MissionCalendar station={station} />
        </>)}
        {searchOpen && <DeepSearchModal scope="division" station={station} onClose={() => setSearchOpen(false)} />}
        {summaryOpen && (
          <TextSummaryModal station={station} start={start} end={end} onClose={() => setSummaryOpen(false)} />
        )}
    </DashboardLayout>
  );
};
