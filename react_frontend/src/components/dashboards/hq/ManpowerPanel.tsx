import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';
import { PanelState } from './panelHelpers';

/**
 * ระบบจัดการกำลังพล (พอร์ตจาก loadHqView('manpower'))
 *
 * ยอดที่ผู้บังคับบัญชาใช้จริงคือ "ปฏิบัติจริง" = ฐาน - ไปช่วย + มาช่วย ไม่ใช่ยอดฐาน
 * เพราะสถานีที่ส่งคนไปช่วยที่อื่นครึ่งหนึ่งมีกำลังพลบนกระดาษเท่าเดิมแต่ทำงานได้ครึ่งเดียว
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
  homeStationLabel?: string;
}

const LEVELS: { key: 'level1' | 'level2' | 'level3'; label: string }[] = [
  { key: 'level1', label: 'ระดับ สว. ขึ้นไป' },
  { key: 'level2', label: 'ระดับ รอง สว.' },
  { key: 'level3', label: 'ระดับชั้นประทวน' },
];

export const ManpowerPanel: React.FC<{ station: string; canEdit: boolean }> = ({ station, canEdit }) => {
  const { user } = useAuth();
  const [data, setData] = useState<any | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqManpower(station, user?.token);
    if (res.status === 'success') setData(res.data);
    else setError(res.message || 'โหลดข้อมูลกำลังพลไม่สำเร็จ');
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

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
      load();
    } else {
      Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    }
  };

  const overview = data?.overview || {};
  const chart = data?.station?.chart || {};
  const stats = data?.station?.stats || {};
  const stationRows = Object.entries(overview).filter(([id]) => id !== 'total') as [string, any][];

  const card = (p: Person, incoming = false) => (
    <div
      key={p.username}
      className="p-2 rounded d-flex justify-content-between align-items-center gap-2"
      style={{
        background: incoming ? 'rgba(32,201,151,0.12)' : p.status === 'out' ? 'rgba(255,193,7,0.12)' : 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="text-white small text-truncate">{p.name}</div>
        <div className="text-white-50" style={{ fontSize: '.72rem' }}>
          {p.code && <span className="me-2">รหัส {p.code}</span>}
          {p.phone}
        </div>
        {incoming && <div className="text-success" style={{ fontSize: '.72rem' }}>มาช่วยจาก {p.homeStationLabel}</div>}
        {!incoming && p.status === 'out' && <div className="text-warning" style={{ fontSize: '.72rem' }}>ไปช่วย {p.tag}</div>}
        {p.remark && <div className="text-white-50 fst-italic" style={{ fontSize: '.72rem' }}>{p.remark}</div>}
      </div>
      {canEdit && !incoming && (
        <button className="btn btn-sm btn-outline-info py-0 px-2" onClick={() => editPerson(p)} title="แก้สถานะช่วยราชการ">
          <i className="fa-solid fa-pen"></i>
        </button>
      )}
    </div>
  );

  return (
    <>
      <div className="glass-card mb-4">
        <h5 className="text-white mb-3"><i className="fa-solid fa-users text-primary"></i> ยอดกำลังพลรายสถานีทั้งกองกำกับการ</h5>
        <PanelState busy={busy} error={error} empty={!busy && !error && !stationRows.length} emptyText="ไม่พบข้อมูลกำลังพล" />

        {!busy && !error && !!stationRows.length && (
          <div className="table-responsive">
            <table className="table table-hq table-bordered text-center align-middle small mb-0">
              <thead>
                <tr>
                  <th className="text-start">หน่วย</th>
                  <th>ยอดฐาน</th>
                  <th className="text-warning">ไปช่วยราชการ</th>
                  <th className="text-success">มาช่วยราชการ</th>
                  <th className="text-info">ปฏิบัติจริง</th>
                </tr>
              </thead>
              <tbody>
                {stationRows.map(([id, row]) => (
                  <tr key={id}>
                    <td className="text-start text-white">{row.name}</td>
                    <td>{row.base}</td>
                    <td className={row.out ? 'text-warning' : ''}>{row.out}</td>
                    <td className={row.in ? 'text-success' : ''}>{row.in}</td>
                    <td className="fw-bold text-info">{row.net}</td>
                  </tr>
                ))}
                {overview.total && (
                  <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <td className="text-start text-warning fw-bold">รวมทั้ง กก.</td>
                    <td className="fw-bold">{overview.total.base}</td>
                    <td className="fw-bold text-warning">{overview.total.out}</td>
                    <td className="fw-bold text-success">{overview.total.in}</td>
                    <td className="fw-bold text-info">{overview.total.net}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!busy && !error && data?.station && (
        <div className="glass-card">
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <h5 className="text-white m-0"><i className="fa-solid fa-sitemap text-info"></i> ผังกำลังพล {overview[station]?.name || station}</h5>
            <div className="small text-white-50">
              ฐาน {stats.base} · ไปช่วย <span className="text-warning">{stats.out}</span> ·
              มาช่วย <span className="text-success">{stats.in}</span> ·
              ปฏิบัติจริง <span className="text-info fw-bold">{stats.net}</span>
            </div>
          </div>

          {LEVELS.map(({ key, label }) => (
            <div className="mb-3" key={key}>
              <div className="small text-white-50 mb-2 border-bottom border-secondary pb-1">
                {label} ({(chart[key] || []).length})
              </div>
              {(chart[key] || []).length ? (
                <div className="d-flex flex-wrap gap-2">
                  {(chart[key] as Person[]).map((p) => (
                    <div key={p.username} style={{ minWidth: 230, flex: '1 1 230px' }}>{card(p)}</div>
                  ))}
                </div>
              ) : (
                <div className="text-white-50 small fst-italic">ไม่มีเจ้าหน้าที่ในระดับนี้</div>
              )}
            </div>
          ))}

          {!!(chart.incoming || []).length && (
            <div>
              <div className="small text-success mb-2 border-bottom border-secondary pb-1">
                กำลังเสริมจากหน่วยอื่น ({chart.incoming.length})
              </div>
              <div className="d-flex flex-wrap gap-2">
                {(chart.incoming as Person[]).map((p) => (
                  <div key={p.username} style={{ minWidth: 230, flex: '1 1 230px' }}>{card(p, true)}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
};
