import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import {
  getNowDateTimeLocal,
  formatPreviewDate,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

export const AccidentForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units } = useStationData();
  const [f, setF] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(),
    unitId: '',
    route: '',
    km: '',
    direction: 'ขาเข้า',
    locDetails: '',
    deadCount: '',
    injuredCount: '',
    hospital: '',
    mainVehicle: '',
    oppVehicle: '',
    cHuman: '',
    cVehicle: '',
    cRoad: '',
    cEnv: '',
    solutions: '',
    govDamage: '',
    propDamageValue: '',
    carNumber: '',
    jointUnits: '',
    description: '',
    lat: '',
    lng: '',
  });
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  const getLocation = () => {
    if (!navigator.geolocation) {
      Swal.fire('แจ้งเตือน', 'เบราว์เซอร์ไม่รองรับ GPS', 'warning');
      return;
    }
    loadingModal('กำลังดึงพิกัดจุดเกิดเหตุ...');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setF((p) => ({ ...p, lat: String(pos.coords.latitude), lng: String(pos.coords.longitude) }));
        Swal.close();
      },
      () => Swal.fire('เกิดข้อผิดพลาด', 'ไม่สามารถดึงตำแหน่งได้ โปรดเปิด GPS', 'error'),
      { enableHighAccuracy: true },
    );
  };

  const submit = async () => {
    const required = ['unitId', 'route', 'km', 'locDetails', 'mainVehicle', 'oppVehicle', 'govDamage', 'carNumber', 'jointUnits', 'description', 'lat', 'lng'];
    if (required.some((k) => !f[k])) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลที่จำเป็นให้ครบถ้วน', 'warning');
      return;
    }
    const dateText = formatPreviewDate(f.reportDateTime);
    const locText = `ทล.${f.route} กม.${f.km} (${f.direction}) ${f.locDetails}`;
    const previewText =
      `📌 [แบบร่างรายงานอุบัติเหตุ]\n\nหน่วยบริการ: ${f.unitId}\nวันที่: ${dateText}\nสถานที่: ${locText}\n` +
      `รถหลัก: ${f.mainVehicle}\nคู่กรณี: ${f.oppVehicle}\n\nตาย: ${f.deadCount || '0'} ราย | เจ็บ: ${f.injuredCount || '0'} ราย\n\n` +
      `(ข้อความแบบเต็มพร้อมคัดลอกจะแสดงหลังบันทึกสำเร็จ)`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังประมวลผลและอัปโหลดไฟล์...');
    const payload = { ...f, stationId: user?.station, actionBy: user?.username };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('accident', payload, user?.token, { files: attachments });
    if (res.status === 'success') {
      await showLineCopyResult(res.message || 'บันทึกรายงานอุบัติเหตุสำเร็จ', res.lineText || previewText, copied);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  const NowBtn = () => (
    <button type="button" className="btn btn-outline-warning" onClick={() => set('reportDateTime', getNowDateTimeLocal())} title="ใช้เวลาปัจจุบัน">
      <i className="fa-solid fa-clock-rotate-left"></i>
    </button>
  );

  return (
    <FormShell title="รายงานอุบัติเหตุ" onBack={onBack} maxWidth={900}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #ffc107' }}>
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วันที่เวลาที่เกิดเหตุ</label>
            <div className="d-flex gap-2 align-items-stretch">
              <input type="datetime-local" className="form-control" value={f.reportDateTime} onChange={(e) => set('reportDateTime', e.target.value)} />
              <NowBtn />
            </div>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">หน่วยรายงาน *</label>
            <select className="form-select border-warning" value={f.unitId} onChange={(e) => set('unitId', e.target.value)} required>
              <option value="">-- เลือกหน่วยรายงาน --</option>
              {units.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>

          <div className="col-12"><hr className="border-secondary" /><label className="text-warning small mb-2">3. สถานที่เกิดเหตุ</label></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">ทล.</label><input type="text" className="form-control" placeholder="เช่น 1" value={f.route} onChange={(e) => set('route', e.target.value)} /></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">กม.</label><input type="text" className="form-control" placeholder="เช่น 580+400" value={f.km} onChange={(e) => set('km', e.target.value)} /></div>
          <div className="col-12 col-md-2"><label className="form-label small text-white-50">ทิศทาง</label>
            <select className="form-select" value={f.direction} onChange={(e) => set('direction', e.target.value)}>
              <option value="ขาเข้า">ขาเข้า</option><option value="ขาออก">ขาออก</option>
            </select>
          </div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ต. / อ. / จว.</label><input type="text" className="form-control" placeholder="ต.วังจันทร์ อ.สามเงา จ.ตาก" value={f.locDetails} onChange={(e) => set('locDetails', e.target.value)} /></div>

          <div className="col-12"><hr className="border-secondary" /><label className="text-warning small mb-2">4. ผู้เสียชีวิต / ผู้ได้รับบาดเจ็บ</label></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">เสียชีวิต (ราย)</label><input type="text" className="form-control" placeholder="ระบุจำนวน หรือ ใส่ -" value={f.deadCount} onChange={(e) => set('deadCount', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ได้รับบาดเจ็บ (ราย)</label><input type="text" className="form-control" placeholder="ระบุจำนวน หรือ ใส่ -" value={f.injuredCount} onChange={(e) => set('injuredCount', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">นำตัวส่ง รพ.</label><input type="text" className="form-control" placeholder="ระบุชื่อ รพ. หรือ ใส่ -" value={f.hospital} onChange={(e) => set('hospital', e.target.value)} /></div>

          <div className="col-12"><hr className="border-secondary" /><label className="text-warning small mb-2">5. รถที่เกิดเหตุ</label></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">รถหลัก (ประเภทและทะเบียน)</label><input type="text" className="form-control border-info" placeholder="เช่น รถบรรทุก 10 ล้อ ทะเบียน 70-8717 ลำปาง" value={f.mainVehicle} onChange={(e) => set('mainVehicle', e.target.value)} /></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">คู่กรณี (ประเภทและทะเบียน)</label><input type="text" className="form-control border-danger" placeholder="ระบุคู่กรณี หรือ พิมพ์ 'ไม่มีคู่กรณี'" value={f.oppVehicle} onChange={(e) => set('oppVehicle', e.target.value)} /></div>

          <div className="col-12"><hr className="border-secondary" /><label className="text-warning small mb-2">6. สรุปสาเหตุ (%)</label></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">พฤติกรรมคน (%)</label><input type="number" className="form-control text-center" placeholder="80" value={f.cHuman} onChange={(e) => set('cHuman', e.target.value)} /></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">สภาพรถ (%)</label><input type="number" className="form-control text-center" placeholder="20" value={f.cVehicle} onChange={(e) => set('cVehicle', e.target.value)} /></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">สภาพถนน (%)</label><input type="number" className="form-control text-center" placeholder="-" value={f.cRoad} onChange={(e) => set('cRoad', e.target.value)} /></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">สภาพแวดล้อม (%)</label><input type="number" className="form-control text-center" placeholder="-" value={f.cEnv} onChange={(e) => set('cEnv', e.target.value)} /></div>

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12"><label className="form-label small text-white-50">7. แนวทางแก้ไข (ใส่ขีด - ขึ้นบรรทัดใหม่ตามต้องการ)</label><textarea className="form-control" rows={3} placeholder="- กวดขันวินัยการจราจร&#10;- ติดตั้งป้ายสัญญาณจราจร..." value={f.solutions} onChange={(e) => set('solutions', e.target.value)} /></div>

          <div className="col-12 col-md-6"><label className="form-label small text-white-50">8. ความเสียหาย</label><input type="text" className="form-control" placeholder="ไม่มี หรือ มี (ระบุรายละเอียดและราคา)" value={f.govDamage} onChange={(e) => set('govDamage', e.target.value)} /></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">8.1 มูลค่าทรัพย์สินเสียหายรวม (บาท)</label><input type="number" className="form-control" min="0" placeholder="เช่น 50000" value={f.propDamageValue} onChange={(e) => set('propDamageValue', e.target.value)} /></div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">9. รถวิทยุตำรวจทางหลวงที่ ว.4</label><input type="text" className="form-control" placeholder="เช่น 5115" value={f.carNumber} onChange={(e) => set('carNumber', e.target.value)} /></div>
          <div className="col-12"><label className="form-label small text-white-50">10. หน่วยร่วมปฏิบัติ</label><input type="text" className="form-control" placeholder="เช่น ตำรวจ สภ.สามเงา, กู้ภัยวังจันทร์" value={f.jointUnits} onChange={(e) => set('jointUnits', e.target.value)} /></div>

          <div className="col-12"><label className="form-label small text-white-50">รายละเอียดอุบัติเหตุ (พฤติการณ์)</label><textarea className="form-control" rows={4} placeholder="ระบุเหตุการณ์ตั้งแต่ต้นจนจบ..." value={f.description} onChange={(e) => set('description', e.target.value)} /></div>

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12 col-md-5"><label className="form-label small text-white-50">ละติจูด</label><input type="text" className="form-control" value={f.lat} onChange={(e) => set('lat', e.target.value)} /></div>
          <div className="col-12 col-md-5"><label className="form-label small text-white-50">ลองจิจูด</label><input type="text" className="form-control" value={f.lng} onChange={(e) => set('lng', e.target.value)} /></div>
          <div className="col-12 col-md-2 d-flex align-items-end"><button type="button" className="btn btn-outline-success w-100" onClick={getLocation}><i className="fa-solid fa-location-crosshairs"></i> ดึงพิกัด</button></div>

          <div className="col-12 mt-3"><label className="form-label small text-white-50">แนบภาพถ่ายที่เกิดเหตุ (เลือกได้หลายภาพ)</label><input type="file" className="form-control" multiple accept="image/*" onChange={(e) => setFiles(e.target.files)} /></div>

          <div className="col-12 mt-4"><button type="button" className="btn btn-warning w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={submit}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button></div>
        </div>
      </div>
    </FormShell>
  );
};
