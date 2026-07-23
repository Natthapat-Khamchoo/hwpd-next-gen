import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import { getNowDateTimeLocal, filesToBase64, loadingModal } from '../../utils/formHelpers';
import Swal from 'sweetalert2';

export const DocumentForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { users } = useStationData();
  const [f, setF] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(),
    subject: '',
    docType: 'บันทึกข้อความ',
    senderName: '',
  });
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!f.subject || !f.senderName || !files || files.length === 0) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกหัวข้อ ผู้ส่ง และแนบไฟล์เอกสาร', 'warning');
      return;
    }
    loadingModal('กำลังบันทึกเอกสาร...');
    const attachments = await filesToBase64(files);
    const payload = { ...f, unitId: user?.unit, stationId: user?.station, actionBy: user?.username };
    const res = await api.submitReport('document', payload, user?.token, { files: attachments });
    if (res.status === 'success') {
      await Swal.fire('สำเร็จ!', res.message || 'บันทึกเอกสารเข้าสู่ระบบเรียบร้อย', 'success');
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="เซ็นเอกสารออนไลน์" onBack={onBack} maxWidth={620}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #00f2ff' }}>
        <div className="row g-3">
          <div className="col-12">
            <label className="form-label small text-white-50">วันที่เวลาที่ส่งเอกสาร</label>
            <div className="d-flex gap-2 align-items-stretch">
              <input type="datetime-local" className="form-control" value={f.reportDateTime} onChange={(e) => set('reportDateTime', e.target.value)} />
              <button type="button" className="btn btn-outline-info" onClick={() => set('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button>
            </div>
          </div>
          <div className="col-12"><label className="form-label small text-white-50">เรื่อง / หัวข้อเอกสาร (ที่จะให้ลงนาม)</label><input type="text" className="form-control border-info" placeholder="เช่น ขออนุมัติเบิกค่าน้ำมันเชื้อเพลิง" value={f.subject} onChange={(e) => set('subject', e.target.value)} /></div>
          <div className="col-12"><label className="form-label small text-white-50">ประเภทเอกสาร</label>
            <select className="form-select" value={f.docType} onChange={(e) => set('docType', e.target.value)}>
              <option value="บันทึกข้อความ">บันทึกข้อความ</option><option value="หนังสือส่งภายนอก">หนังสือส่งภายนอก</option><option value="แบบขออนุมัติ">แบบขออนุมัติ</option><option value="อื่นๆ">อื่นๆ</option>
            </select>
          </div>
          <div className="col-12"><label className="form-label small text-white-50">ผู้ส่งเอกสาร</label>
            <select className="form-select" value={f.senderName} onChange={(e) => set('senderName', e.target.value)}><option value="">-- เลือกรายชื่อ --</option>{users.map((u) => <option key={u} value={u}>{u}</option>)}</select>
          </div>
          <div className="col-12 mt-3">
            <label className="form-label small text-info"><i className="fa-solid fa-cloud-arrow-up"></i> แนบไฟล์เอกสาร (PDF/Word/รูปภาพ)</label>
            <input type="file" className="form-control" accept=".pdf,.doc,.docx,image/*" onChange={(e) => setFiles(e.target.files)} />
            <p className="text-white-50" style={{ fontSize: '0.7rem' }}>* ข้อมูลจะถูกบันทึกไว้ในระบบฐานข้อมูลสถานี เพื่อรอการตรวจสอบและจัดพิมพ์</p>
          </div>
          <div className="col-12 mt-4"><button type="button" className="btn-primary-custom" onClick={submit}><i className="fa-solid fa-floppy-disk"></i> บันทึกเอกสารเข้าสู่ระบบ</button></div>
        </div>
      </div>
    </FormShell>
  );
};
