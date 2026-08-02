import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { PanelState, RangePicker, recentStart, today } from './panelHelpers';
import { ReportExportPanel } from '../ReportExportPanel';

/**
 * แฟ้มข้อมูลรายวัน (พอร์ตจาก loadHqView('daily_detail'))
 *
 * รวมทุกรายงานที่อนุมัติแล้วมาไว้ไทม์ไลน์เดียว เรียงตามวันแล้วตามเวลา ฝอ. ใช้หน้านี้
 * ไล่ดูว่าแต่ละวันหน่วยไหนทำอะไรไปบ้างก่อนสรุปขึ้น กก. — ตัวกรองประเภทกับหน่วยจึง
 * กรองในเครื่อง ไม่ยิงใหม่ทุกครั้ง เพราะข้อมูลทั้งช่วงโหลดมาครบแล้ว
 */

interface Row {
  recordId: string;
  sheetName: string;
  rawDate: string;
  time: string;
  type: string;
  station: string;
  unit: string;
  details: string;
  reporter: string;
  link: string;
}

const TYPE_COLORS: Record<string, string> = {
  'ผลการปฏิบัติ': 'text-primary',
  'จับกุม': 'text-danger',
  'อุบัติเหตุ': 'text-warning',
  'ว.4 อื่นๆ/จิตอาสา': 'text-info',
  'รับเสด็จ': 'text-success',
};

interface Props {
  station: string;
  reports: { reportKey: string; title: string; cadence: string }[];
  /** ออก Excel ได้เฉพาะระดับ บก. เพราะตัวสร้างไฟล์รวมยอดทั้ง 8 กก. ไว้ในไฟล์เดียว */
  canExport: boolean;
}

export const DailyDetailPanel: React.FC<Props> = ({ station, reports, canExport }) => {
  const { user } = useAuth();
  const [start, setStart] = useState(recentStart());
  const [end, setEnd] = useState(today());
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [stationFilter, setStationFilter] = useState('');

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.hqDailyDetail(station, start, end, user?.token);
    if (res.status === 'success') setRows(res.data || []);
    else setError(res.message || 'โหลดรายละเอียดรายวันไม่สำเร็จ');
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station]);

  const types = useMemo(() => Array.from(new Set(rows.map((r) => r.type))), [rows]);
  const stations = useMemo(() => Array.from(new Set(rows.map((r) => r.station))), [rows]);
  const filtered = rows.filter(
    (r) => (!typeFilter || r.type === typeFilter) && (!stationFilter || r.station === stationFilter),
  );

  // จัดกลุ่มตามวัน ไทม์ไลน์แบบไม่มีหัววันอ่านยากมากเมื่อช่วงเกินหนึ่งสัปดาห์
  const byDate = useMemo(() => {
    const map = new Map<string, Row[]>();
    filtered.forEach((r) => map.set(r.rawDate, [...(map.get(r.rawDate) || []), r]));
    return Array.from(map.entries());
  }, [filtered]);

  return (
    <>
      <div className="glass-card mb-4">
        <h5 className="text-white mb-1"><i className="fa-solid fa-folder-open text-success"></i> แฟ้มข้อมูลรายวัน</h5>
        <p className="text-white-50 small mb-3">ทุกรายงานที่ผ่านการอนุมัติแล้วในช่วงวันที่ที่เลือก</p>

        <RangePicker start={start} end={end} onStart={setStart} onEnd={setEnd} onLoad={load} busy={busy} />

        {!busy && !error && !!rows.length && (
          <div className="d-flex flex-wrap gap-2 mb-3">
            <select className="form-select form-select-sm bg-dark text-white border-secondary" style={{ width: 200 }}
                    value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">ทุกประเภทรายงาน</option>
              {types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select className="form-select form-select-sm bg-dark text-white border-secondary" style={{ width: 220 }}
                    value={stationFilter} onChange={(e) => setStationFilter(e.target.value)}>
              <option value="">ทุกหน่วย</option>
              {stations.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <span className="text-white-50 small align-self-center">แสดง {filtered.length} จาก {rows.length} รายการ</span>
          </div>
        )}

        <PanelState busy={busy} error={error} empty={!busy && !error && !filtered.length}
                    emptyText={rows.length ? 'ไม่มีรายการที่ตรงกับตัวกรอง' : 'ไม่มีรายงานที่อนุมัติแล้วในช่วงวันที่ที่เลือก'} />

        {!busy && !error && !!filtered.length && (
          <div style={{ maxHeight: 620, overflowY: 'auto' }}>
            {byDate.map(([date, items]) => (
              <div className="mb-3" key={date}>
                <div className="small text-info border-bottom border-secondary pb-1 mb-2">
                  <i className="fa-solid fa-calendar-day"></i> {date} ({items.length} รายการ)
                </div>
                <div className="table-responsive">
                  <table className="table table-hq table-bordered align-middle small mb-0">
                    <thead>
                      <tr><th style={{ width: 64 }}>เวลา</th><th style={{ width: 130 }}>ประเภท</th>
                          <th className="text-start" style={{ width: 170 }}>หน่วย</th>
                          <th className="text-start">รายละเอียด</th>
                          <th className="text-start" style={{ width: 150 }}>ผู้รายงาน</th>
                          <th style={{ width: 50 }}>ไฟล์</th></tr>
                    </thead>
                    <tbody>
                      {items.map((r) => (
                        <tr key={r.recordId}>
                          <td>{r.time}</td>
                          <td className={TYPE_COLORS[r.type] || ''}>{r.type}</td>
                          <td className="text-start">{r.station}<div className="text-white-50" style={{ fontSize: '.72rem' }}>{r.unit}</div></td>
                          <td className="text-start text-white-50" style={{ whiteSpace: 'pre-wrap' }}>{r.details}</td>
                          <td className="text-start">{r.reporter}</td>
                          <td>
                            {r.link && String(r.link).startsWith('http')
                              ? <a href={r.link} target="_blank" rel="noreferrer" className="text-info"><i className="fa-solid fa-folder-open"></i></a>
                              : <span className="text-white-50">-</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {canExport ? (
        <ReportExportPanel reports={reports} />
      ) : (
        <div className="glass-card w-100 p-4">
          <h5 className="text-white mb-1"><i className="fa-solid fa-file-excel text-success"></i> ออกรายงานเป็น Excel</h5>
          <p className="text-white-50 small mb-0">
            แบบฟอร์มที่ระบบออกให้อัตโนมัติเป็นรายงานรวมทั้ง 8 กองกำกับการในไฟล์เดียว จึงออกได้ที่ระดับ
            บก.ทล. เท่านั้น ระดับ กก. ใช้ตารางด้านบนดูรายการแล้วคัดลอกเฉพาะส่วนที่ต้องการได้
          </p>
        </div>
      )}
    </>
  );
};
