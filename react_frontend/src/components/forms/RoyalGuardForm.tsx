import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import {
  getNowDateTimeLocal,
  getFrontendStationData,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

const THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
const dateParts = (s?: string): { d: string; t: string } => {
  if (!s || !s.includes('T')) return { d: s || '-', t: '' };
  const [datePart, timePart] = s.split('T');
  const [y, m, d] = datePart.split('-');
  const yy = (parseInt(y) + 543).toString().slice(-2);
  return { d: `${parseInt(d)} ${THAI_MONTHS[parseInt(m) - 1]} ${yy}`, t: timePart.slice(0, 5).replace(':', '.') };
};

export const RoyalGuardForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { users } = useStationData();
  const [type, setType] = useState<'prep' | 'complete'>('prep');
  const [f, setF] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(),
    missionName: '',
    carNumbers: '',
    targetCount: '',
    details: '',
  });
  const [commanders, setCommanders] = useState<string[]>(['']);
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));
  const setCmd = (i: number, v: string) => setCommanders((prev) => prev.map((c, idx) => (idx === i ? v : c)));
  const addCmd = () => setCommanders((prev) => [...prev, '']);
  const removeCmd = (i: number) => setCommanders((prev) => prev.filter((_, idx) => idx !== i));

  const submit = async () => {
    const cmds = commanders.filter(Boolean);
    if (!f.reportDateTime || !f.missionName || !f.details) {
      Swal.fire('แจ้งเตือน', 'กรุณากรอกข้อมูลสำคัญให้ครบถ้วน', 'warning');
      return;
    }
    if (cmds.length === 0) {
      Swal.fire('แจ้งเตือน', 'กรุณาเลือกผู้บังคับบัญชาอย่างน้อย 1 ท่าน', 'warning');
      return;
    }
    const st = getFrontendStationData(user?.station);
    const dt = dateParts(f.reportDateTime);
    const cmdText = cmds.join(', ');
    const stationNum = user?.station || '51';
    let previewText: string;
    if (type === 'prep') {
      previewText =
        `${st.p} : รายงานภารกิจถวายความปลอดภัย ${f.missionName}\nเรียน   ผู้บังคับบัญชา\nวันนี้ ${dt.d}\nเวลา   ${dt.t} น.\n` +
        `${cmdText}\nตรวจความพร้อมชี้แจงภารกิจ  กำลังพลภารกิจ ${f.details}\nและซักซ้อมขบวนรถ\n- เส้นทางทุกที่หมาย \n` +
        `- เส้นทางฉุกเฉินทางการแพทย์ \n- เส้นทางพื้นที่ปลอดภัย\n      เหตุการณ์เรียบร้อย                \n` +
        `จึงเรียนมาเพื่อโปรดทราบ  \n          ${stationNum}\n    (${st.p})\n\nไฟล์แนบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;
    } else {
      previewText =
        `📌เรียน ผู้บังคับบัญชา\n${st.f}\n\n          วันที่ ${dt.d}\n${cmdText}\n` +
        `   ภารกิจ ถปภ. ชุดปฎิบัติ รถวิทยุ ${f.carNumbers} ${f.missionName} \n` +
        `  ขออนุญาตรายงานเหตุการณ์และผลการปฏิบัติหน้าที่รักษาความปลอดภัย ดังนี้ \n\n${f.details}\n\n` +
        ` ระหว่างปฏิบัติหน้าที่เหตุการณ์ทั่วไปปกติ\n\n     จึงเรียนมาเพื่อโปรดทราบ\n             ( ${st.p} )\n\nไฟล์แนบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;
    }

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังส่งข้อมูล...');
    const payload = {
      actionBy: user?.username, stationId: user?.station, unitId: user?.unit, reportType: type,
      reportDateTime: f.reportDateTime, missionName: f.missionName, commanders: cmdText,
      carNumbers: f.carNumbers, targetCount: f.targetCount, details: f.details,
    };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('royal-guard', payload, user?.token, { files: attachments });
    if (res.status === 'success') {
      await showLineCopyResult(res.message || 'บันทึกรายงานรับเสด็จสำเร็จ', res.lineText || previewText, copied);
      onBack();
    } else {
      Swal.fire('เกิดข้อผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="หมวดรายงานรับเสด็จ" onBack={onBack} maxWidth={700}>
      <div className="glass-card w-100">
        <div className="btn-group w-100 mb-4" role="group">
          <input type="radio" className="btn-check" name="rgType" id="rgTypePrep" checked={type === 'prep'} onChange={() => setType('prep')} />
          <label className="btn btn-outline-warning" htmlFor="rgTypePrep"><i className="fa-solid fa-users"></i> 1. ปล่อยแถวรับเสด็จ</label>
          <input type="radio" className="btn-check" name="rgType" id="rgTypeComplete" checked={type === 'complete'} onChange={() => setType('complete')} />
          <label className="btn btn-outline-success" htmlFor="rgTypeComplete"><i className="fa-solid fa-flag-checkered"></i> 2. เสร็จสิ้นภารกิจ</label>
        </div>

        <div className="row g-3 mb-3">
          <div className="col-12 col-md-6">
            <label className="form-label text-warning small">วันที่และเวลา</label>
            <div className="d-flex gap-2 align-items-stretch">
              <input type="datetime-local" className="form-control" value={f.reportDateTime} onChange={(e) => set('reportDateTime', e.target.value)} />
              <button type="button" className="btn btn-outline-warning" onClick={() => set('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button>
            </div>
          </div>
          <div className="col-12 col-md-6"><label className="form-label text-warning small">ชื่อภารกิจถวายความปลอดภัย</label><input type="text" className="form-control" placeholder="เช่น เดโชชัย 5..." value={f.missionName} onChange={(e) => set('missionName', e.target.value)} /></div>

          <div className="col-12">
            <label className="form-label text-info small">รายชื่อผู้บังคับบัญชา</label>
            {commanders.map((c, i) => (
              <div className="d-flex gap-2 mb-2" key={i}>
                <select className="form-select" value={c} onChange={(e) => setCmd(i, e.target.value)}>
                  <option value="">-- เลือกผู้บังคับบัญชา --</option>
                  {users.map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
                {commanders.length > 1 && (
                  <button type="button" className="btn btn-outline-danger" onClick={() => removeCmd(i)}><i className="fa-solid fa-trash"></i></button>
                )}
              </div>
            ))}
            <button type="button" className="btn btn-outline-info btn-sm mt-2 w-100" onClick={addCmd}><i className="fa-solid fa-plus"></i> เพิ่มผู้บังคับบัญชาท่านอื่น</button>
          </div>
        </div>

        {type === 'complete' && (
          <div className="row g-3 mb-3">
            <div className="col-12 col-md-6"><label className="form-label text-warning small">ชุดปฏิบัติ รถวิทยุ (ระบุหมายเลข)</label><input type="text" className="form-control" placeholder="เช่น 0192 2306 2302..." value={f.carNumbers} onChange={(e) => set('carNumbers', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-warning small">จำนวนที่หมายในพื้นที่ตนเอง (แห่ง)</label><input type="number" className="form-control" placeholder="ระบุตัวเลข (ถ้ามี)" value={f.targetCount} onChange={(e) => set('targetCount', e.target.value)} /></div>
          </div>
        )}

        <div className="mb-3">
          <label className="form-label text-warning small">{type === 'complete' ? 'ไทม์ไลน์เหตุการณ์ (เวลาและสถานที่)' : 'ภารกิจของพระองค์'}</label>
          <textarea className="form-control" rows={4} value={f.details} onChange={(e) => set('details', e.target.value)}
            placeholder={type === 'complete' ? 'เวลา 14.28 น. เดโชชัย 5 ไมค์ 11 ว.22 สนาม ฮ...' : 'พิมพ์รายละเอียดที่นี่...'} />
          <div className="form-text text-white-50">{type === 'complete' ? 'พิมพ์เวลาและเหตุการณ์แต่ละช่วงลงมาทีละบรรทัด' : 'เช่น ถปภ.เดโชชัย 5 เสด็จพระราชดำเนินแทนพระองค์...'}</div>
        </div>

        <div className="mb-4">
          <label className="form-label text-warning small"><i className="fa-solid fa-camera"></i> แนบรูปภาพ (ถ้ามี)</label>
          <input className="form-control" type="file" accept="image/*" multiple onChange={(e) => setFiles(e.target.files)} />
          <small className="text-muted d-block mt-1">เลือกได้หลายรูป</small>
        </div>

        <button type="button" className="btn-primary-custom" onClick={submit}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button>
      </div>
    </FormShell>
  );
};
