import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import {
  getNowDateTimeLocal,
  getFrontendStationData,
  formatPreviewDate,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

export const MissionForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units } = useStationData();
  const [f, setF] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(),
    startTime: '',
    endTime: '',
    missionDetails: '',
    location: '',
  });
  const [selectedUnits, setSelectedUnits] = useState<string[]>([]);
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));
  const toggleUnit = (u: string) =>
    setSelectedUnits((prev) => (prev.includes(u) ? prev.filter((x) => x !== u) : [...prev, u]));

  const submit = async () => {
    if (!f.startTime || !f.endTime || !f.missionDetails || !f.location) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลภารกิจให้ครบถ้วน', 'warning');
      return;
    }
    if (selectedUnits.length === 0) {
      Swal.fire('แจ้งเตือน', 'กรุณาเลือกหน่วยบริการที่เกี่ยวข้องอย่างน้อย 1 หน่วย', 'warning');
      return;
    }
    const st = getFrontendStationData(user?.station);
    const unitsText = selectedUnits.join(', ');
    const previewText =
      `${st.f} แจ้งภารกิจ\nวันที่แจ้งภารกิจ ${formatPreviewDate(f.reportDateTime)}\nแจ้งหน่วยบริการ ${unitsText}\n` +
      `ภารกิจ ${f.missionDetails}\nวันที่เวลาภารกิจ ตั้งแต่ ${formatPreviewDate(f.startTime)} ถึง ${formatPreviewDate(f.endTime)}\n` +
      `สถานที่ ${f.location}\nไฟล์ประกอบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึกและส่งแจ้งภารกิจ...');
    const payload = { ...f, unitId: user?.unit, stationId: user?.station, actionBy: user?.username };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('mission', payload, user?.token, { files: attachments, selectedUnits });
    if (res.status === 'success') {
      await showLineCopyResult(res.message || 'แจ้งภารกิจสำเร็จ', res.lineText || previewText, copied);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="แจ้งภารกิจ" onBack={onBack}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #198754' }}>
        <div className="row g-3">
          <div className="col-12">
            <label className="form-label small text-white-50">วันที่เวลาที่รายงานแจ้งภารกิจ</label>
            <div className="d-flex gap-2 align-items-stretch">
              <input type="datetime-local" className="form-control" value={f.reportDateTime} onChange={(e) => set('reportDateTime', e.target.value)} />
              <button type="button" className="btn btn-outline-success" onClick={() => set('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button>
            </div>
          </div>
          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาเริ่มภารกิจ (ตั้งแต่)</label><input type="datetime-local" className="form-control border-success" value={f.startTime} onChange={(e) => set('startTime', e.target.value)} /></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาสิ้นสุดภารกิจ (ถึง)</label><input type="datetime-local" className="form-control border-success" value={f.endTime} onChange={(e) => set('endTime', e.target.value)} /></div>
          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12">
            <label className="form-label small text-success fw-bold mb-2">หน่วยบริการที่เกี่ยวข้อง (เลือกได้มากกว่า 1 หน่วย)</label>
            <div className="p-3 rounded" style={{ background: 'rgba(25, 135, 84, 0.1)', border: '1px solid rgba(25, 135, 84, 0.3)' }}>
              <div className="row">
                {units.length === 0 && <div className="col-12 text-center text-white-50 small">กำลังโหลดรายชื่อหน่วยบริการ...</div>}
                {units.map((u, i) => (
                  <div className="col-6 col-md-4 mb-2" key={u}>
                    <div className="form-check">
                      <input className="form-check-input" type="checkbox" id={`unit_${i}`} checked={selectedUnits.includes(u)} onChange={() => toggleUnit(u)} />
                      <label className="form-check-label text-white" htmlFor={`unit_${i}`}>{u}</label>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="col-12 mt-3"><label className="form-label small text-white-50">รายละเอียดภารกิจ</label><textarea className="form-control" rows={3} placeholder="ระบุรายละเอียดภารกิจที่ต้องการสั่งการ..." value={f.missionDetails} onChange={(e) => set('missionDetails', e.target.value)} /></div>
          <div className="col-12"><label className="form-label small text-white-50">สถานที่</label><input type="text" className="form-control" placeholder="ระบุสถานที่ปฏิบัติภารกิจ" value={f.location} onChange={(e) => set('location', e.target.value)} /></div>
          <div className="col-12 mt-3"><label className="form-label small text-white-50">แนบไฟล์ประกอบภารกิจ (คำสั่ง/แผนที่/รูปภาพ - เลือกได้หลายไฟล์)</label><input type="file" className="form-control" multiple accept="image/*,application/pdf" onChange={(e) => setFiles(e.target.files)} /></div>
          <div className="col-12 mt-4"><button type="button" className="btn btn-success w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={submit}><i className="fa-solid fa-paper-plane"></i> ยืนยันแจ้งภารกิจ</button></div>
        </div>
      </div>
    </FormShell>
  );
};
