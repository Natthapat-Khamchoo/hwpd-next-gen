import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { downloadSheet } from './excel';
import { PanelState } from './panelHelpers';

/**
 * ระบบจัดการกำลังพล (พอร์ตจาก loadHQManpowerOverview + viewHQStationManpower)
 *
 * ยอดที่ผู้บังคับบัญชาใช้จริงคือ "ปฏิบัติจริง" = ฐาน - ไปช่วย + มาช่วย ไม่ใช่ยอดฐาน
 * เพราะสถานีที่ส่งคนไปช่วยที่อื่นครึ่งหนึ่งมีกำลังพลบนกระดาษเท่าเดิมแต่ทำงานได้ครึ่งเดียว
 *
 * ผังกำลังพลเปิดดูได้ทุกสถานีในกอง ไม่ใช่แค่สถานีของคนที่ล็อกอิน — ของเดิมมีปุ่ม
 * "จัดการ/ดูผัง" ต่อแถว เพราะงานของ ฝอ. คือดูแลกำลังพลทั้งกอง
 */

interface Person {
  username: string;
  name: string;
  status?: string;
  tag?: string;
  remark: string;
  phone: string;
  code: string;
  rawOutStation?: string;
  rawStart?: string;
  rawEnd?: string;
  homeStation?: string;
  homeStationLabel?: string;
}

const LEVELS: { key: 'level1' | 'level2' | 'level3'; label: string }[] = [
  { key: 'level1', label: 'ระดับ สว. ขึ้นไป' },
  { key: 'level2', label: 'ระดับ รอง สว.' },
  { key: 'level3', label: 'ระดับชั้นประทวน' },
];

export const ManpowerPanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [overview, setOverview] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  // สถานีที่กำลังกางผังอยู่ ปิดไว้ตั้งแต่แรกเหมือนของเดิม (hqOrgChartArea display:none)
  const [chartStation, setChartStation] = useState('');
  const [chart, setChart] = useState<any | null>(null);
  const [chartBusy, setChartBusy] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);

  const loadOverview = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqManpower(station, user?.token);
    if (res.status === 'success') setOverview(res.data.overview || {});
    else setError(res.message || 'โหลดข้อมูลกำลังพลไม่สำเร็จ');
    setBusy(false);
  };

  useEffect(() => { loadOverview(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

  const openChart = async (stationId: string) => {
    setChartStation(stationId);
    setChartBusy(true);
    setChart(null);
    const res = await api.hqManpower(stationId, user?.token);
    setChartBusy(false);
    if (res.status === 'success') setChart(res.data.station);
    else Swal.fire('โหลดผังไม่สำเร็จ', res.message || '', 'error');
  };

  /**
   * ผังทำเนียบกำลังพลที่หน่วยทำไว้เป็นรูป (สแกน/ออกแบบเอง) คนละอย่างกับผังที่ระบบ
   * สร้างจาก tb_Users — ของเดิมเก็บลิงก์ไว้ในตัวแปร STATION_CHART_IMAGES ในหน้าเว็บ
   * ที่นี่อ่านจาก config ฝั่ง server จึงเพิ่มสถานีใหม่ได้โดยไม่ต้อง deploy หน้าเว็บใหม่
   */
  const openImage = () => {
    if (chart?.chartImageUrl) return setImageOpen(true);
    Swal.fire({
      icon: 'info',
      title: 'ยังไม่มีรูปภาพ',
      html: 'ยังไม่ได้ตั้งลิงก์รูปผังของสถานีนี้ในระบบครับ<br><br>' +
        '<small style="color:#9ca3af">วิธีเพิ่ม: อัปโหลดรูปลง Google Drive ตั้งเป็นแชร์แบบสาธารณะ ' +
        'แล้วนำลิงก์รูปแบบ <code>https://lh3.googleusercontent.com/d/รหัสไฟล์</code> ' +
        'ไปใส่เป็น <code>chartImageUrl</code> ของสถานีนั้นใน <code>STATION_SECRETS_JSON</code></small>',
      confirmButtonText: 'เข้าใจแล้ว',
    });
  };

  const editPerson = async (p: Person) => {
    const { value } = await Swal.fire({
      title: `<span style="font-size:1rem">${p.name}</span>`,
      html: `
        <div style="text-align:left;margin-top:8px">
          <label style="font-size:.8rem;color:#9ca3af">รหัสสถานีที่ไปช่วยราชการ (เว้นว่าง = ยกเลิก)</label>
          <input id="mpStation" class="swal2-input" placeholder="เช่น 52" value="${p.rawOutStation || ''}" style="margin:.25rem 0 1rem">
          <label style="font-size:.8rem;color:#9ca3af">วันที่เริ่ม</label>
          <input id="mpStart" type="date" class="swal2-input" value="${p.rawStart || ''}" style="margin:.25rem 0 1rem">
          <label style="font-size:.8rem;color:#9ca3af">วันที่สิ้นสุด</label>
          <input id="mpEnd" type="date" class="swal2-input" value="${p.rawEnd || ''}" style="margin:.25rem 0 1rem">
          <label style="font-size:.8rem;color:#9ca3af">หมายเหตุ</label>
          <input id="mpRemark" class="swal2-input" value="${p.remark || ''}" style="margin:.25rem 0 0">
        </div>`,
      showCancelButton: true,
      confirmButtonText: 'บันทึก',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#0066ff',
      preConfirm: () => ({
        helpStationId: (document.getElementById('mpStation') as HTMLInputElement)?.value.trim(),
        startDate: (document.getElementById('mpStart') as HTMLInputElement)?.value,
        endDate: (document.getElementById('mpEnd') as HTMLInputElement)?.value,
        remark: (document.getElementById('mpRemark') as HTMLInputElement)?.value,
      }),
    });
    if (!value) return;

    const res = await api.hqSaveManpowerStatus({ username: p.username, ...value }, user?.token);
    if (res.status === 'success') {
      await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
      loadOverview();
      if (chartStation) openChart(chartStation);
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const stationRows = Object.entries(overview).filter(([id]) => id !== 'total') as [string, any][];
  const total = overview.total;

  const exportExcel = () => {
    downloadSheet('กำลังพลรายสถานี', [
      ['สรุปกำลังพลระดับกองกำกับการ'],
      [],
      ['หน่วย/สถานี', 'อัตรา', 'ไปช่วยราชการ', 'มาช่วยราชการ', 'ปฏิบัติงานจริง'],
      ...stationRows.map(([, r]) => [r.name, r.base, r.out, r.in, r.net]),
      ...(total ? [['รวมทั้ง กก.', total.base, total.out, total.in, total.net]] : []),
    ], 'กำลังพล');
  };

  /** การ์ดรายชื่อ ใช้คลาส org-card ของต้นฉบับ ป้ายไป/มาช่วยราชการลอยมุมบนขวา */
  const card = (p: Person, incoming = false) => (
    <div
      key={p.username}
      className={`org-card${incoming ? ' in' : p.status === 'out' ? ' out' : ''}`}
      style={canEdit && !incoming ? undefined : { cursor: 'default' }}
      onClick={() => canEdit && !incoming && editPerson(p)}
    >
      {incoming && <span className="org-card-badge badge-in">มาช่วย</span>}
      {!incoming && p.status === 'out' && <span className="org-card-badge badge-out">ไปช่วย</span>}

      <div className="org-card-title text-truncate" title={p.name}>{p.name}</div>
      <div className="text-white-50" style={{ fontSize: '.75rem' }}>
        {p.code && <span className="me-2">รหัส {p.code}</span>}{p.phone}
      </div>
      {incoming && <div className="text-success mt-1" style={{ fontSize: '.75rem' }}>จาก {p.homeStationLabel}</div>}
      {!incoming && p.status === 'out' && <div className="text-danger mt-1" style={{ fontSize: '.75rem' }}>{p.tag}</div>}
      {p.remark && <div className="text-white-50 fst-italic mt-1" style={{ fontSize: '.72rem' }}>{p.remark}</div>}
    </div>
  );

  return (
    <>
      <div className="glass-card mb-4">
        <h5 className="text-primary mb-3"><i className="fa-solid fa-users"></i> ภาพรวมกำลังพลระดับกองกำกับการ</h5>

        {total && (
          <div className="row g-3 mb-4">
            {[
              { l: 'ยอดรวมทั้งกองกำกับ (นาย)', v: total.base, c: 'text-primary' },
              { l: 'ไปช่วยราชการทั้งหมด (นาย)', v: total.out, c: 'text-danger' },
              { l: 'มาช่วยราชการทั้งหมด (นาย)', v: total.in, c: 'text-success' },
              { l: 'กำลังพลปฏิบัติงานจริง (นาย)', v: total.net, c: 'text-info' },
            ].map((k, i) => (
              <div className="col-md-3 col-6" key={i}>
                <div className="kpi-card" style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <div className="title">{k.l}</div><div className={`value ${k.c}`}>{k.v}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3 border-bottom border-secondary pb-3">
          <h6 className="text-white m-0"><i className="fa-solid fa-list"></i> สรุปยอดแยกตามสถานี</h6>
          <div className="d-flex gap-2">
            <button className="btn btn-sm btn-success fw-bold" onClick={exportExcel} disabled={!stationRows.length}>
              <i className="fa-solid fa-file-excel"></i> Export
            </button>
            <button className="btn btn-sm btn-outline-info" onClick={loadOverview}>
              <i className="fa-solid fa-rotate"></i> รีเฟรช
            </button>
          </div>
        </div>

        <PanelState busy={busy} error={error} empty={!busy && !error && !stationRows.length} emptyText="ไม่พบข้อมูลกำลังพล" />

        {!busy && !error && !!stationRows.length && (
          <div className="table-responsive">
            <table className="table table-hq table-bordered text-center align-middle small mb-0">
              <thead>
                <tr>
                  <th className="text-start">หน่วย/สถานี</th>
                  <th className="text-primary">อัตรา</th>
                  <th className="text-danger">ไปช่วยราชการ</th>
                  <th className="text-success">มาช่วยราชการ</th>
                  <th className="text-info">ปฏิบัติงานจริง</th>
                  <th style={{ width: 130 }}>จัดการ / ดูผัง</th>
                </tr>
              </thead>
              <tbody>
                {stationRows.map(([id, row]) => (
                  <tr key={id} style={chartStation === id ? { background: 'rgba(13,202,240,0.08)' } : undefined}>
                    <td className="text-start text-white">{row.name}</td>
                    <td>{row.base}</td>
                    <td className={row.out ? 'text-danger' : ''}>{row.out}</td>
                    <td className={row.in ? 'text-success' : ''}>{row.in}</td>
                    <td className="fw-bold text-info">{row.net}</td>
                    <td>
                      <button className="btn btn-sm btn-outline-info py-0 px-2" onClick={() => openChart(id)}>
                        <i className="fa-solid fa-sitemap"></i> ดูผัง
                      </button>
                    </td>
                  </tr>
                ))}
                {total && (
                  <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <td className="text-start text-warning fw-bold">รวมทั้ง กก.</td>
                    <td className="fw-bold">{total.base}</td>
                    <td className="fw-bold text-danger">{total.out}</td>
                    <td className="fw-bold text-success">{total.in}</td>
                    <td className="fw-bold text-info">{total.net}</td>
                    <td></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {chartStation && (
        <div className="glass-card">
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <h5 className="text-info m-0">
              <i className="fa-solid fa-sitemap"></i> ทำเนียบกำลังพล: {overview[chartStation]?.name || chartStation}
            </h5>
            <div className="d-flex align-items-center gap-3">
              {chart && (
                <div className="small text-white-50">
                  ฐาน {chart.stats.base} · ไปช่วย <span className="text-danger">{chart.stats.out}</span> ·
                  มาช่วย <span className="text-success">{chart.stats.in}</span> ·
                  ปฏิบัติจริง <span className="text-info fw-bold">{chart.stats.net}</span>
                </div>
              )}
              <button className="btn btn-sm btn-outline-info" onClick={openImage}>
                <i className="fa-solid fa-image"></i> ดูผังรูปภาพต้นฉบับ
              </button>
              <button className="btn btn-sm btn-outline-secondary" onClick={() => { setChartStation(''); setChart(null); }}>
                <i className="fa-solid fa-xmark"></i> ปิดผัง
              </button>
            </div>
          </div>

          <PanelState busy={chartBusy} error="" empty={false} emptyText="" />

          {chart && (
            <div className="org-chart">
              {LEVELS.map(({ key, label }) => (
                <div className="mb-3" key={key}>
                  <div className="small text-white-50 mb-2 border-bottom border-secondary pb-1">
                    {label} ({(chart.chart[key] || []).length})
                  </div>
                  {(chart.chart[key] || []).length ? (
                    <div className="org-level">
                      {(chart.chart[key] as Person[]).map((p) => card(p))}
                    </div>
                  ) : (
                    <div className="text-white-50 small fst-italic">ไม่มีเจ้าหน้าที่ในระดับนี้</div>
                  )}
                </div>
              ))}

              {!!(chart.chart.incoming || []).length && (
                <div>
                  <div className="small text-success mb-2 border-bottom border-secondary pb-1">
                    กำลังเสริมจากหน่วยอื่น ({chart.chart.incoming.length})
                  </div>
                  <div className="org-level">
                    {(chart.chart.incoming as Person[]).map((p) => card(p, true))}
                  </div>
                </div>
              )}

              {canEdit && (
                <div className="text-center mt-4 border-top border-secondary pt-3">
                  <span className="badge bg-dark border border-secondary text-white-50 p-2">
                    <i className="fa-solid fa-hand-pointer text-info"></i> คลิกที่การ์ดรายชื่อ เพื่อแก้ไขสถานะ ไปช่วย/มาช่วย ราชการ
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {imageOpen && chart?.chartImageUrl && (
        <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.85)' }} onClick={() => setImageOpen(false)}>
          <div className="modal-dialog modal-xl modal-dialog-centered" onClick={(e) => e.stopPropagation()}>
            <div className="modal-content bg-dark border border-secondary">
              <div className="modal-header border-secondary">
                <h6 className="modal-title text-info">
                  <i className="fa-solid fa-image"></i> ผังทำเนียบกำลังพล: {overview[chartStation]?.name || chartStation}
                </h6>
                <button className="btn-close btn-close-white" onClick={() => setImageOpen(false)}></button>
              </div>
              <div className="modal-body text-center">
                <img src={chart.chartImageUrl} alt="ผังทำเนียบกำลังพล"
                     style={{ maxWidth: '100%', borderRadius: 8 }} />
              </div>
              <div className="modal-footer border-secondary">
                <a className="btn btn-outline-info btn-sm" href={chart.chartImageUrl} target="_blank" rel="noreferrer">
                  <i className="fa-solid fa-up-right-from-square"></i> เปิดในแท็บใหม่
                </a>
                <button className="btn btn-secondary btn-sm" onClick={() => setImageOpen(false)}>ปิด</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
