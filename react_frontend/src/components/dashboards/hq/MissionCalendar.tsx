import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { PanelState, currentMonth } from './panelHelpers';

/**
 * ปฏิทินภารกิจ (พอร์ตจาก getCommanderCalendarData)
 *
 * ผู้กำกับการใช้ดูว่าเดือนนี้ กก. รับภารกิจซ้อนกันวันไหนบ้าง วันที่มีภารกิจจึงต้อง
 * เห็นได้จากตารางปฏิทินโดยไม่ต้องกด แล้วค่อยกดดูรายละเอียดของวันนั้น
 */

interface Mission {
  recordId: string;
  stationId: string;
  stationName: string;
  unitId: string;
  startTime: string;
  endTime: string | null;
  targetUnits: string;
  details: string;
  location: string;
}

const DAY_LABELS = ['อา', 'จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส'];
const timeOf = (iso: string) => (iso || '').slice(11, 16) || '--:--';

export const MissionCalendar: React.FC<{ station: string }> = ({ station }) => {
  const { user } = useAuth();
  const [month, setMonth] = useState(currentMonth());
  const [missions, setMissions] = useState<Mission[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');

  const load = async () => {
    setBusy(true);
    setError('');
    setSelected('');
    const res = await api.commanderCalendar(station, month, user?.token);
    if (res.status === 'success') setMissions(res.data || []);
    else setError(res.message || 'โหลดปฏิทินภารกิจไม่สำเร็จ');
    setBusy(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [station, month]);

  const byDay = useMemo(() => {
    const map = new Map<string, Mission[]>();
    missions.forEach((m) => {
      const day = (m.startTime || '').slice(0, 10);
      if (day) map.set(day, [...(map.get(day) || []), m]);
    });
    return map;
  }, [missions]);

  // ช่องว่างหน้าวันที่ 1 เพื่อให้คอลัมน์ตรงกับวันในสัปดาห์จริง
  const [year, mon] = month.split('-').map(Number);
  const firstWeekday = new Date(year, mon - 1, 1).getDay();
  const daysInMonth = new Date(year, mon, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const dayKey = (d: number) => `${month}-${String(d).padStart(2, '0')}`;
  const selectedMissions = selected ? byDay.get(selected) || [] : [];

  return (
    <div className="glass-card mb-4">
      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
        <h5 className="text-white m-0"><i className="fa-solid fa-calendar-days text-warning"></i> ปฏิทินภารกิจประจำเดือน</h5>
        <div className="d-flex align-items-center gap-2">
          <span className="small text-white-50">{missions.length} ภารกิจ</span>
          <input type="month" className="form-control form-control-sm bg-dark text-white border-warning"
                 style={{ width: 175 }} value={month} onChange={(e) => setMonth(e.target.value)} />
        </div>
      </div>

      <PanelState busy={busy} error={error} empty={false} emptyText="" />

      {!busy && !error && (
        <>
          <div className="d-grid" style={{ gridTemplateColumns: 'repeat(7,1fr)', gap: 6 }}>
            {DAY_LABELS.map((d) => (
              <div key={d} className="text-center text-white-50 small pb-1">{d}</div>
            ))}
            {cells.map((day, i) => {
              if (day === null) return <div key={`pad-${i}`} />;
              const key = dayKey(day);
              const items = byDay.get(key) || [];
              const isSelected = selected === key;
              return (
                <div
                  key={key}
                  onClick={() => items.length && setSelected(isSelected ? '' : key)}
                  className="p-2 rounded text-center"
                  style={{
                    minHeight: 58,
                    cursor: items.length ? 'pointer' : 'default',
                    background: isSelected ? 'rgba(250,204,21,0.25)' : items.length ? 'rgba(250,204,21,0.10)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${isSelected ? '#facc15' : 'rgba(255,255,255,0.08)'}`,
                  }}
                >
                  <div className={items.length ? 'text-warning fw-bold' : 'text-white-50'}>{day}</div>
                  {!!items.length && <div className="text-white" style={{ fontSize: '.7rem' }}>{items.length} ภารกิจ</div>}
                </div>
              );
            })}
          </div>

          {!missions.length && (
            <p className="text-white-50 small mt-3 mb-0">ไม่มีภารกิจที่แจ้งไว้ในเดือนนี้</p>
          )}

          {!!selectedMissions.length && (
            <div className="mt-3">
              <div className="small text-warning border-bottom border-secondary pb-1 mb-2">
                ภารกิจวันที่ {selected} ({selectedMissions.length} รายการ)
              </div>
              <div className="table-responsive">
                <table className="table table-sc table-bordered align-middle small mb-0">
                  <thead>
                    <tr><th style={{ width: 110 }}>เวลา</th><th className="text-start" style={{ width: 170 }}>หน่วย</th>
                        <th className="text-start">รายละเอียด</th><th className="text-start" style={{ width: 180 }}>สถานที่</th></tr>
                  </thead>
                  <tbody>
                    {selectedMissions.map((m) => (
                      <tr key={m.recordId}>
                        <td className="text-nowrap">{timeOf(m.startTime)}{m.endTime && ` - ${timeOf(m.endTime)}`}</td>
                        <td className="text-start">{m.stationName}<div className="text-white-50" style={{ fontSize: '.72rem' }}>{m.unitId}</div></td>
                        <td className="text-start text-white-50" style={{ whiteSpace: 'pre-wrap' }}>{m.details || '-'}</td>
                        <td className="text-start text-white-50">{m.location || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
