import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { useFormDraft } from '../../hooks/useFormDraft';
import { FormShell } from './FormShell';
import { DraftNotice } from './DraftNotice';
import { LocationPickerButton } from '../common/LocationPickerButton';
import { ThaiDateInput } from './ThaiDateInput';
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

/** เวลาปัจจุบัน + n ชั่วโมง ในรูปแบบเดียวกับช่อง datetime-local */
const hoursFromNow = (n: number): string => {
  const t = new Date(Date.now() + n * 3600 * 1000);
  const pad = (v: number) => String(v).padStart(2, '0');
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}T${pad(t.getHours())}:${pad(t.getMinutes())}`;
};

export const CheckpointForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units, users, phoneMap } = useStationData();
  const blank = {
    reportDateTime: getNowDateTimeLocal(),
    unitId: '',
    dutyOfficer: '',
    totalPersonnel: '',
    carNumber: '',
    location: '',
    locationOther: '',
    lat: '',
    lng: '',
    // ช่วงเวลาที่ด่านเปิดจริง หน้าภาพรวมระดับประเทศใช้ค่านี้ตัดสินว่าหมุดไหน
    // ยังตั้งอยู่ ตั้งค่าเริ่มต้นเป็นตอนนี้ถึงอีกสามชั่วโมงซึ่งเป็นผลัดปกติ
    startTime: getNowDateTimeLocal(),
    endTime: hoursFromNow(3),
  };
  const [f, setF, draft] = useFormDraft('checkpoint', blank, user?.username);
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  const resetForm = () => {
    draft.clear();
    setF({ ...blank, reportDateTime: getNowDateTimeLocal(), startTime: getNowDateTimeLocal(), endTime: hoursFromNow(3) });
  };

  const getLocation = () => {
    if (!navigator.geolocation) {
      Swal.fire('แจ้งเตือน', 'เบราว์เซอร์ไม่รองรับ GPS', 'warning');
      return;
    }
    loadingModal('กำลังดึงพิกัด...');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setF((p) => ({ ...p, lat: String(pos.coords.latitude), lng: String(pos.coords.longitude) }));
        Swal.close();
      },
      () => Swal.fire('ผิดพลาด', 'ดึงพิกัดไม่สำเร็จ กรุณาปักหมุดบนแผนที่แทน', 'error'),
      { enableHighAccuracy: true },
    );
  };

  const submit = async () => {
    if (!f.unitId || !f.dutyOfficer || !f.totalPersonnel || !f.carNumber || !f.location) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลที่มีเครื่องหมาย * ให้ครบถ้วน', 'warning');
      return;
    }
    if (f.location === 'อื่นๆ' && !f.locationOther) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณาระบุสถานที่ตั้งด่าน', 'warning');
      return;
    }
    // ข้อ 16 บังคับกรอกพิกัด ถ้าปล่อยว่างได้ ด่านจะขึ้นแผนที่ไม่ครบและสถิติเชิงพื้นที่
    // จะอ่านไม่ได้ตั้งแต่ต้น
    if (!f.lat || !f.lng) {
      Swal.fire('ยังไม่ได้ระบุพิกัด', 'กรุณากดปักหมุดบนแผนที่ หรือดึงพิกัดปัจจุบันของจุดตั้งด่าน', 'warning');
      return;
    }
    // หน้าภาพรวมของ ผบก. ใช้ช่วงเวลานี้ตัดสินว่าด่านไหนยังตั้งอยู่ ปล่อยว่างไม่ได้
    if (!f.startTime || !f.endTime) {
      Swal.fire('ยังไม่ได้ระบุช่วงเวลา', 'กรุณาระบุเวลาที่เริ่มตั้งด่านและเวลาที่เลิกด่าน', 'warning');
      return;
    }
    if (f.endTime <= f.startTime) {
      Swal.fire('ช่วงเวลาไม่ถูกต้อง', 'เวลาเลิกด่านต้องอยู่หลังเวลาเริ่มตั้งด่าน', 'warning');
      return;
    }
    const st = getFrontendStationData(user?.station);
    const finalLocation = f.location === 'อื่นๆ' ? f.locationOther : f.location;
    const dateText = formatPreviewDate(f.reportDateTime);
    const previewText =
      `เรียน ผู้บังคับบัญชา\nกองบัญชาการตำรวจสอบสวนกลาง(CIB)​\nโดย ${st.f} (${st.p})\nวันนี้ ${dateText}\n` +
      `หน่วยบริการฯตำรวจทางหลวง ${f.unitId}\nรถวิทยุ ${f.carNumber}\n` +
      `${f.dutyOfficer} พร้อมพวกรวม ${f.totalPersonnel} นาย ตั้ง ว.43 อาญา/จราจร \n` +
      `บริเวณ ${finalLocation} ผลการปฏิบัติจะรายงานให้ทราบต่อไป\n` +
      `ตั้งด่านตั้งแต่เวลา ${formatPreviewDate(f.startTime)} ถึง ${formatPreviewDate(f.endTime)}\n` +
      `\nจึงเรียนมาเพื่อโปรดทราบ\n    (${st.p})\n` +
      `ไฟล์แนบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึกรายงานด่าน...');
    const payload = { ...f, location: finalLocation, stationId: user?.station, actionBy: user?.username };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('checkpoint', payload, user?.token, { files: attachments });
    if (res.status === 'success') {
      // ล้างร่างทันทีที่บันทึกสำเร็จ ไม่งั้นค่าที่ส่งไปแล้วจะกลับมาอีกรอบตอนเปิดฟอร์มใหม่
      draft.clear();
      await showLineCopyResult(res.message || 'บันทึกรายงานด่านสำเร็จ', res.lineText || previewText, copied ? previewText : undefined);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="รายงานด่าน จุดตรวจ จุดสกัด" onBack={onBack} backLabel="กลับ">
      <div className="glass-card w-100">
        {draft.restored && <DraftNotice onClear={resetForm} />}
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label>
            <div className="d-flex gap-2 align-items-stretch">
              <ThaiDateInput type="datetime-local" value={f.reportDateTime} onChange={(v) => set('reportDateTime', v)} />
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

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12">
            <span className="badge bg-info text-dark mb-2">
              <i className="fa-solid fa-clock"></i> ช่วงเวลาที่ตั้งด่าน
            </span>
            <div className="small text-white-50 mb-2">
              หน้าภาพรวมของ ผบก.ทล. จะแสดงหมุดสีเขียวเฉพาะด่านที่ยังอยู่ในช่วงเวลานี้
            </div>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">เริ่มตั้งด่าน *</label>
            <ThaiDateInput type="datetime-local" value={f.startTime} onChange={(v) => set('startTime', v)} />
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">เลิกด่าน *</label>
            <ThaiDateInput type="datetime-local" value={f.endTime} onChange={(v) => set('endTime', v)} />
          </div>

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">ละติจูด *</label>
            <input type="text" className="form-control" placeholder="เช่น 16.8765" value={f.lat} onChange={(e) => set('lat', e.target.value)} required />
          </div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">ลองจิจูด *</label>
            <input type="text" className="form-control" placeholder="เช่น 98.5432" value={f.lng} onChange={(e) => set('lng', e.target.value)} required />
          </div>
          <div className="col-6 col-md-2 d-flex align-items-end">
            <button type="button" className="btn btn-outline-success w-100" onClick={getLocation}>
              <i className="fa-solid fa-location-crosshairs"></i> ดึงพิกัด
            </button>
          </div>
          <div className="col-6 col-md-2 d-flex align-items-end">
            <LocationPickerButton
              lat={f.lat}
              lng={f.lng}
              title="ปักหมุดจุดตั้งด่าน"
              label="ปักหมุด"
              onSelect={(lat, lng) => setF((p) => ({ ...p, lat, lng }))}
            />
          </div>

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
