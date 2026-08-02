import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import Swal from 'sweetalert2';

/**
 * รายงานสรุปผลการปฏิบัติเป็นข้อความ พร้อมคัดลอกไปวางใน LINE
 * (พอร์ตจาก generateTextSummaryAndCopy + modalTextSummary)
 *
 * ผู้กำกับการกดปุ่มเดียวแล้วได้ข้อความครบรูปแบบ ไม่ต้องไล่อ่านทีละหน้าแล้วพิมพ์เอง
 * เป็นงานที่ทำทุกวัน จึงเป็นฟีเจอร์ที่ใช้บ่อยที่สุดในหน้านี้
 *
 * ประกอบประโยคที่ฝั่งนี้ ไม่ใช่ที่ server เพราะถ้อยคำเป็นเรื่องการนำเสนอ ปรับได้โดย
 * ไม่ต้อง deploy หลังบ้านใหม่ ส่วน server ส่งมาแต่ตัวเลขดิบ
 */

const THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];

/** 2026-07-31 -> "31 ก.ค. 2569" (พ.ศ. ตามที่ราชการใช้) */
const thaiDate = (iso: string): string => {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getDate()} ${THAI_MONTHS[d.getMonth()]} ${d.getFullYear() + 543}`;
};

const n = (value: number) => Number(value || 0).toLocaleString('th-TH');

const buildText = (d: any, start: string, end: string): string => {
  const t = d.totals;
  const header = start === end ? thaiDate(start) : `${thaiDate(start)} - ${thaiDate(end)}`;
  const lines: string[] = [];

  lines.push('เรียน ผู้บังคับบัญชา');
  lines.push(`ขอรายงานผลการปฏิบัติงานของ กก.${d.division} บก.ทล.`);
  lines.push(`🗓️ ประจำวันที่ ${header}`);
  lines.push('');

  lines.push(`1. ผลการจับกุมคดีอาญา รวม ${n(t.arrests)} ราย`);
  const cats = Object.entries(d.arrestsByCategory || {});
  if (cats.length) {
    lines.push('แบ่งเป็นประเภทฐานความผิด ดังนี้');
    cats.forEach(([name, count]) => lines.push(`- ${name} ${n(count as number)} ราย`));
  }

  lines.push('');
  lines.push(`2. ผลการจับกุมคดีจราจร รวม ${n(t.v20)} ราย`);
  Object.entries(d.charges || {}).forEach(([name, count]) => lines.push(`- ${name} ${n(count as number)} ราย`));

  const escortTotal = (t.escortRoyal || 0) + (t.escortGeneral || 0);
  lines.push('');
  lines.push(`3. นำขบวน รวม ${n(escortTotal)} ขบวน`);
  if (escortTotal) {
    if (t.escortRoyal) lines.push(`- ขบวนเสด็จ ${n(t.escortRoyal)} ขบวน`);
    if (t.escortGeneral) lines.push(`- ขบวนทั่วไปและวีไอพี ${n(t.escortGeneral)} ขบวน`);
  } else {
    lines.push('- ขบวนเสด็จ 0 ขบวน');
    lines.push('- ขบวนทั่วไปและวีไอพี 0 ขบวน');
  }

  lines.push('');
  lines.push(`4. รับแจ้งอุบัติเหตุ รวม ${n(t.accidents)} ครั้ง`);
  (d.accidentsByStation || []).forEach((s: any) => {
    lines.push(`- ${s.name} : เกิดเหตุ ${n(s.incidents)} ครั้ง`);
    lines.push(`  (เสียชีวิต ${n(s.dead)}, บาดเจ็บ ${n(s.injured)})`);
    lines.push(`  มูลค่าความเสียหาย ${s.damages?.length ? s.damages.join(', ') : '0 บาท'}`);
  });

  lines.push('');
  lines.push('5. ตรวจยึดของกลาง');
  const evi = Object.entries(d.evidence || {});
  if (evi.length) {
    evi.forEach(([cat, types]) => {
      const parts = Object.entries(types as any).map(
        ([kind, v]: [string, any]) => `${kind} ${n(v.qty)} ${v.unit || ''}`.trim(),
      );
      lines.push(`- ${cat} (${parts.join(', ')})`);
    });
  } else {
    lines.push('- ไม่มีรายการตรวจยึดของกลางในช่วงเวลานี้');
  }

  lines.push('');
  lines.push(`6. กิจกรรมจิตอาสา ${n(t.volunteer)} ครั้ง`);
  lines.push(`7. ช่วยเหลือ/บริการประชาชน ${n(t.service)} ครั้ง`);
  lines.push('');
  lines.push('จึงเรียนมาเพื่อโปรดทราบ');

  return lines.join('\n');
};

interface Props { station: string; start: string; end: string; onClose: () => void }

export const TextSummaryModal: React.FC<Props> = ({ station, start, end, onClose }) => {
  const { user } = useAuth();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      const res = await api.commanderSummary(station, start, end, user?.token);
      setBusy(false);
      if (res.status !== 'success') return setError(res.message || 'รวบรวมข้อมูลไม่สำเร็จ');
      setText(buildText(res.data, start, end));
    })();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      Swal.fire({
        title: 'คัดลอกสำเร็จ!',
        text: 'ข้อความถูกคัดลอกแล้ว นำไปวางใน LINE ได้เลยครับ',
        icon: 'success',
        timer: 2000,
        showConfirmButton: false,
      });
    } catch {
      // บางเบราว์เซอร์บล็อก clipboard API เมื่อไม่ได้มาจากการกดโดยตรง เลือกข้อความ
      // ให้แทน ผู้ใช้กด Ctrl+C ต่อได้ทันที
      const area = document.getElementById('textSummaryOutput') as HTMLTextAreaElement | null;
      area?.select();
      Swal.fire('คัดลอกอัตโนมัติไม่ได้', 'ระบบเลือกข้อความให้แล้ว กด Ctrl+C เพื่อคัดลอกครับ', 'info');
    }
  };

  return (
    <div className="modal d-block" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={onClose}>
      <div className="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable" onClick={(e) => e.stopPropagation()}>
        <div className="modal-content bg-dark border border-secondary">
          <div className="modal-header border-secondary">
            <h6 className="modal-title text-white">
              <i className="fa-solid fa-file-lines text-warning"></i> สรุปผลการปฏิบัติงาน
            </h6>
            <button className="btn-close btn-close-white" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            {busy && <div className="text-white-50 small py-4 text-center">กำลังรวบรวมข้อมูล...</div>}
            {error && <div className="alert alert-danger py-2 small mb-0">{error}</div>}
            {!busy && !error && (
              <textarea
                id="textSummaryOutput"
                className="form-control bg-dark text-white border-secondary"
                style={{ minHeight: 420, fontFamily: 'inherit', fontSize: '.85rem', lineHeight: 1.7 }}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            )}
            {!busy && !error && (
              <p className="text-white-50 small mt-2 mb-0">แก้ข้อความในกล่องได้ก่อนคัดลอก</p>
            )}
          </div>
          <div className="modal-footer border-secondary">
            <button className="btn btn-secondary btn-sm" onClick={onClose}>ปิด</button>
            <button className="btn btn-success btn-sm fw-bold" onClick={copy} disabled={busy || !!error}>
              <i className="fa-solid fa-copy"></i> คัดลอกข้อความ
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
