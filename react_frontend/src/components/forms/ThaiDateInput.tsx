import React, { useEffect, useRef } from 'react';
import flatpickr from 'flatpickr';
import { Thai } from 'flatpickr/dist/l10n/th.js';
import 'flatpickr/dist/flatpickr.min.css';
import 'flatpickr/dist/themes/dark.css';

const THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];

// Desktop = pointer:fine + wide screen. On mobile/touch we keep the native
// picker (better touch UX); on desktop we use flatpickr with a Thai พ.ศ. calendar.
const isDesktop = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(min-width: 769px)').matches &&
  !window.matchMedia('(pointer: coarse)').matches;

interface Props {
  type?: 'date' | 'datetime-local';
  value: string;
  onChange: (v: string) => void;
  className?: string;
  id?: string;
}

/**
 * Date / datetime field. Value is ISO ("YYYY-MM-DD" or "YYYY-MM-DDTHH:mm") on
 * both platforms, so form logic is unchanged. Desktop shows a Buddhist-year
 * (พ.ศ.) flatpickr calendar; mobile uses the native input.
 */
export const ThaiDateInput: React.FC<Props> = ({ type = 'date', value, onChange, className = 'form-control', id }) => {
  const ref = useRef<HTMLInputElement>(null);
  const fpRef = useRef<flatpickr.Instance | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const desktop = useRef(isDesktop());

  useEffect(() => {
    if (!desktop.current || !ref.current) return;
    const isDateTime = type === 'datetime-local';
    const thaiFormat = (date: Date, format: string): string => {
      const pad = (n: number) => String(n).padStart(2, '0');
      const d = date.getDate();
      const m = THAI_MONTHS[date.getMonth()];
      const y = (date.getFullYear() + 543).toString().slice(-2);
      if (format === 'th-datetime') return `${d} ${m} ${y} ${pad(date.getHours())}:${pad(date.getMinutes())} น.`;
      if (format === 'th-date') return `${d} ${m} ${y}`;
      return flatpickr.formatDate(date, format);
    };
    const fp = flatpickr(ref.current, {
      locale: Thai,
      disableMobile: true,
      enableTime: isDateTime,
      time_24hr: true,
      dateFormat: isDateTime ? 'Y-m-d\\TH:i' : 'Y-m-d',
      altInput: true,
      altInputClass: className,
      altFormat: isDateTime ? 'th-datetime' : 'th-date',
      formatDate: thaiFormat,
      defaultDate: value || undefined,
      onChange: (_sel, dateStr) => onChangeRef.current(dateStr),
      onReady: (_s, _d, inst) => { if (inst.currentYearElement) inst.currentYearElement.value = String(inst.currentYear + 543); },
      onYearChange: (_s, _d, inst) => { if (inst.currentYearElement) inst.currentYearElement.value = String(inst.currentYear + 543); },
      onMonthChange: (_s, _d, inst) => { if (inst.currentYearElement) inst.currentYearElement.value = String(inst.currentYear + 543); },
    });
    fpRef.current = fp;
    return () => { fp.destroy(); fpRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  // Reflect external value changes (e.g. the "เวลาปัจจุบัน" button) into flatpickr.
  useEffect(() => {
    const fp = fpRef.current;
    if (desktop.current && fp && value !== fp.input.value) {
      fp.setDate(value || '', false);
    }
  }, [value]);

  if (!desktop.current) {
    return <input id={id} type={type} className={className} value={value} onChange={(e) => onChange(e.target.value)} />;
  }

  /*
   * บนเดสก์ท็อป flatpickr สร้างช่องภาษาไทย (altInput) ขึ้นมาอีกช่องแล้วซ่อนช่องนี้ไว้
   * เก็บค่า ISO — แต่มันซ่อนด้วยการสั่ง `input.type = "hidden"` ใส่ DOM ตรง ๆ
   *
   * React เป็นเจ้าของ element นี้และเขียน `type` ทับทุกครั้งที่ re-render ช่องที่ควร
   * ซ่อนจึงกลับมาแสดงพร้อมค่าดิบ "2026-08-04T21:11" คู่กับช่องไทย เห็นเป็นสองช่อง
   *
   * อาการโผล่ช้าราวหนึ่งวินาทีหลังเปิดฟอร์ม เพราะต้องรอ re-render รอบแรกซึ่งมาจาก
   * useStationData โหลด dropdown เสร็จ ตอนกดเข้าหน้าใหม่ ๆ จึงยังดูปกติอยู่
   *
   * ประกาศ type="hidden" ตรงนี้เลย ให้ React เป็นคนยืนยันค่าซ่อนทุกรอบ แทนที่จะ
   * ปล่อยให้สองฝ่ายแย่งกันเขียน — flatpickr ตั้งค่าเดิมซ้ำก็ไม่มีผลอะไร
   */
  return <input id={id} ref={ref} type="hidden" className={className} defaultValue={value} />;
};
