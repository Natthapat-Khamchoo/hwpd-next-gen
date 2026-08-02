import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { PanelState, currentMonth } from './panelHelpers';

/**
 * ปฏิทินปฏิบัติการ (พอร์ตจาก initOperationCalendar / renderCalendarGrid / renderAgendaView)
 *
 * ผู้กำกับการใช้ดูว่าเดือนนี้ กก. รับภารกิจซ้อนกันวันไหนบ้าง จุดสีในช่องวันบอกว่าเป็น
 * ของสถานีไหน — เห็นได้ทันทีว่าวันนั้นกระจุกอยู่ที่สถานีเดียวหรือกระจายทั้งกอง
 * ซึ่งข้อความ "3 ภารกิจ" เฉย ๆ บอกไม่ได้
 *
 * สีประจำสถานีใช้เลขหลักที่สองของรหัส (X0 = ฝอ.) จึงใช้ได้ทุก กก. ต่างจากต้นฉบับ
 * ที่ฮาร์ดโค้ด st-color-5X ไว้เฉพาะ กก.5
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
const THAI_MONTHS = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
  'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'];

/** ภารกิจที่กรอกมาแต่วันที่ไม่มีเวลา ให้ขึ้นว่า "ทั้งวัน" ไม่ใช่ --:-- ซึ่งอ่านเหมือนข้อมูลเสีย */
const timeOf = (iso: string) => (iso || '').slice(11, 16);
const stationTone = (stationId: string) => stationId.slice(-1) || '0';

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

  /** เลื่อนเดือนไปข้างหน้า/ถอยหลัง โดยไม่ให้เดือน 13 หรือ 0 หลุดออกไป */
  const shiftMonth = (step: number) => {
    const [y, m] = month.split('-').map(Number);
    const d = new Date(y, m - 1 + step, 1);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };

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
  const monthLabel = `${THAI_MONTHS[mon - 1]} ${year + 543}`;

  return (
    <div className="cmd-card mb-4">
      <h5 className="text-white mb-1">
        <i className="fa-solid fa-calendar-days text-warning"></i> ปฏิทินปฏิบัติการ (Master Operation Calendar)
      </h5>
      <p className="small text-white-50 mb-3">คลิกที่วันเพื่อดูภารกิจของวันนั้น · จุดสีคือสถานีที่รับผิดชอบ</p>

      <div className="d-flex justify-content-between align-items-center mb-2">
        <button className="btn btn-sm btn-outline-warning px-3" title="เดือนก่อนหน้า" onClick={() => shiftMonth(-1)}>
          <i className="fa-solid fa-chevron-left"></i>
        </button>
        <div className="text-center">
          <div className="text-white fw-bold">{monthLabel}</div>
          <div className="text-white-50" style={{ fontSize: '.75rem' }}>{missions.length} ภารกิจ</div>
        </div>
        <button className="btn btn-sm btn-outline-warning px-3" title="เดือนถัดไป" onClick={() => shiftMonth(1)}>
          <i className="fa-solid fa-chevron-right"></i>
        </button>
      </div>

      <PanelState busy={busy} error={error} empty={false} emptyText="" />

      {!busy && !error && (
        <>
          <div className="cal-grid">
            {DAY_LABELS.map((d) => <div key={d} className="cal-header">{d}</div>)}
            {cells.map((day, i) => {
              if (day === null) return <div key={`pad-${i}`} className="cal-day empty" />;
              const key = dayKey(day);
              const items = byDay.get(key) || [];
              return (
                <div
                  key={key}
                  className={`cal-day${selected === key ? ' active' : ''}`}
                  onClick={() => items.length && setSelected(selected === key ? '' : key)}
                  style={items.length ? undefined : { cursor: 'default' }}
                >
                  <div className="cal-date-num">{day}</div>
                  <div className="cal-dots-container">
                    {items.map((m) => (
                      <span key={m.recordId} className={`cal-dot st-color-${stationTone(m.stationId)}`}
                            title={`${m.stationName} — ${m.details || 'ภารกิจ'}`} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {!missions.length && (
            <p className="text-white-50 small mt-3 mb-0">ไม่มีภารกิจที่แจ้งไว้ในเดือนนี้</p>
          )}

          {!!selectedMissions.length && (
            <div className="mt-4 border-top border-secondary pt-3">
              <h6 className="text-warning mb-3">
                <i className="fa-solid fa-list-check"></i> ภารกิจประจำวันที่ {selected} ({selectedMissions.length} รายการ)
              </h6>
              {selectedMissions.map((m) => (
                <div key={m.recordId} className={`agenda-card st-${stationTone(m.stationId)}`}>
                  <div className="d-flex justify-content-between align-items-start gap-2">
                    <div className="text-white fw-bold small">{m.stationName}</div>
                    <span className="text-white-50" style={{ fontSize: '.75rem' }}>
                      {timeOf(m.startTime)
                        ? `${timeOf(m.startTime)}${timeOf(m.endTime || '') ? ` - ${timeOf(m.endTime || '')}` : ''}`
                        : 'ทั้งวัน'}
                    </span>
                  </div>
                  {m.unitId && <div className="text-white-50" style={{ fontSize: '.75rem' }}>{m.unitId}</div>}
                  <div className="text-white-50 small mt-1" style={{ whiteSpace: 'pre-wrap' }}>{m.details || '-'}</div>
                  {m.location && (
                    <div className="text-white-50" style={{ fontSize: '.75rem' }}>
                      <i className="fa-solid fa-location-dot"></i> {m.location}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};
