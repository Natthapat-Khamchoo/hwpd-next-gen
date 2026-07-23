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

const LOCATIONS = [
  'หน้าหน่วยบริการสามเงา ทล.1 กม 571-572 ต.วังจันทร์ อ.สามเงา จ.ตาก',
  'หน้าหน่วยฯ คลองขลุง ทล.1 กม. 414-415 ต.คลองขลุง อ.คลองขลุง จ.กำแพงเพชร',
];

export const CheckpointForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units, users, phoneMap } = useStationData();
  const [f, setF] = useState({
    reportDateTime: getNowDateTimeLocal(),
    unitId: '',
    dutyOfficer: '',
    totalPersonnel: '',
    carNumber: '',
    location: '',
    locationOther: '',
  });
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!f.unitId || !f.dutyOfficer || !f.totalPersonnel || !f.carNumber || !f.location) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลที่มีเครื่องหมาย * ให้ครบถ้วน', 'warning');
      return;
    }
    if (f.location === 'อื่นๆ' && !f.locationOther) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณาระบุสถานที่ตั้งด่าน', 'warning');
      return;
    }
    const st = getFrontendStationData(user?.station);
    const finalLocation = f.location === 'อื่นๆ' ? f.locationOther : f.location;
    const dateText = formatPreviewDate(f.reportDateTime);
    const previewText =
      `เรียน ผู้บังคับบัญชา\nกองบัญชาการตำรวจสอบสวนกลาง(CIB)​\nโดย ${st.f} (${st.p})\nวันนี้ ${dateText}\n` +
      `หน่วยบริการฯตำรวจทางหลวง ${f.unitId}\nรถวิทยุ ${f.carNumber}\n` +
      `${f.dutyOfficer} พร้อมพวกรวม ${f.totalPersonnel} นาย ตั้ง ว.43 อาญา/จราจร \n` +
      `บริเวณ ${finalLocation} ผลการปฏิบัติจะรายงานให้ทราบต่อไป\n\nจึงเรียนมาเพื่อโปรดทราบ\n    (${st.p})\n` +
      `ไฟล์แนบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึกรายงานด่าน...');
    const payload = { ...f, location: finalLocation, stationId: user?.station, actionBy: user?.username };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('checkpoint', payload, user?.token, { files: attachments });
    if (res.status === 'success') {
      await showLineCopyResult(res.message || 'บันทึกรายงานด่านสำเร็จ', res.lineText || previewText, copied);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="รายงานด่าน จุดตรวจ จุดสกัด" onBack={onBack} backLabel="กลับ">
      <div className="glass-card w-100">
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label>
            <div className="d-flex gap-2 align-items-stretch">
              <input type="datetime-local" className="form-control" value={f.reportDateTime} onChange={(e) => set('reportDateTime', e.target.value)} />
              <button type="button" className="btn btn-outline-info" onClick={() => set('reportDateTime', getNowDateTimeLocal())} title="ใช้เวลาปัจจุบัน">
                <i className="fa-solid fa-clock-rotate-left"></i>
              </button>
            </div>
          </div>

          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">หน่วยบริการ *</label>
            <select className="form-select" value={f.unitId} onChange={(e) => set('unitId', e.target.value)} required>
              <option value="">-- เลือกหน่วยบริการ --</option>
              {units.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>

          <div className="col-12"><hr className="border-secondary" /></div>

          <div className="col-12 col-md-8">
            <label className="form-label small text-white-50">ผู้ปฏิบัติหน้าที่ประจำหน่วย (ยศ ชื่อ สกุล ตำแหน่ง) *</label>
            <select className="form-select" value={f.dutyOfficer} onChange={(e) => set('dutyOfficer', e.target.value)} required>
              <option value="">-- เลือกรายชื่อ --</option>
              {users.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            {f.dutyOfficer && phoneMap[f.dutyOfficer] && (
              <div className="small text-info mt-1"><i className="fa-solid fa-phone"></i> {phoneMap[f.dutyOfficer]}</div>
            )}
          </div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">จำนวนผู้ปฏิบัติรวม (นาย) *</label>
            <input type="number" className="form-control" placeholder="รวมผู้รายงาน" value={f.totalPersonnel} onChange={(e) => set('totalPersonnel', e.target.value)} required />
          </div>

          <div className="col-12">
            <label className="form-label small text-white-50">รถวิทยุตรวจเขต *</label>
            <input type="text" className="form-control" placeholder="ระบุเลขรถวิทยุ" value={f.carNumber} onChange={(e) => set('carNumber', e.target.value)} required />
          </div>

          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">สถานที่ตั้งด่าน *</label>
            <select className="form-select" value={f.location} onChange={(e) => set('location', e.target.value)} required>
              <option value="">-- เลือกสถานที่ --</option>
              {LOCATIONS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
              <option value="อื่นๆ">อื่นๆ (ระบุเอง)</option>
            </select>
          </div>
          {f.location === 'อื่นๆ' && (
            <div className="col-12 col-md-6">
              <label className="form-label small text-white-50">ระบุสถานที่อื่นๆ</label>
              <input type="text" className="form-control border-info" placeholder="กรอกสถานที่" value={f.locationOther} onChange={(e) => set('locationOther', e.target.value)} />
            </div>
          )}

          <div className="col-12">
            <label className="form-label small text-white-50">แนบภาพประกอบด่าน (เลือกได้หลายไฟล์)</label>
            <input type="file" className="form-control" multiple accept="image/*" onChange={(e) => setFiles(e.target.files)} />
          </div>

          <div className="col-12 mt-4">
            <button type="button" className="btn-primary-custom" onClick={submit}>
              <i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง
            </button>
          </div>
        </div>
      </div>
    </FormShell>
  );
};
