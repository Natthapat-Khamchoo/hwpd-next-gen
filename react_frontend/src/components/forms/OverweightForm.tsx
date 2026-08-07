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
  formatPreviewDate,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

/**
 * รายงานการตรวจสอบรถบรรทุกน้ำหนักเกิน (requirement ข้อ 8)
 *
 * มาแทนเมนู "บันทึกข้อความ" ของผู้ปฏิบัติ ซึ่งเดิมเป็นงานสารบรรณส่งเอกสารให้ลงนาม
 * ข้อมูลเก่ายังอยู่ในตาราง `tb_Documents` และเปิดดูย้อนหลังได้ ส่วนรายงานนี้เขียนลง
 * ตารางใหม่ `tb_OverweightTrucks` และเข้าคิวรออนุมัติเหมือนรายงานผลการปฏิบัติตัวอื่น
 */

/**
 * พิกัดน้ำหนักตามจำนวนเพลาสำหรับ **เติมให้อัตโนมัติเป็นตัวช่วยเท่านั้น**
 * เจ้าหน้าที่แก้ทับได้เสมอ และค่านี้ต้องให้ฝ่ายกฎหมายของหน่วยตรวจก่อนใช้งานจริง
 * เพราะพิกัดจริงขึ้นกับลักษณะรถด้วย ไม่ใช่จำนวนเพลาอย่างเดียว
 */
const LEGAL_WEIGHT_BY_AXLE: Record<string, string> = {
  '2': '15000',
  '3': '25000',
  '4': '30000',
  '5': '37000',
  '6': '45000',
  '7': '47000',
};

const VEHICLE_TYPES = [
  'รถบรรทุก 6 ล้อ',
  'รถบรรทุก 10 ล้อ',
  'รถพ่วง',
  'รถกึ่งพ่วง',
  'รถกึ่งพ่วงบรรทุกวัสดุยาว',
  'อื่นๆ',
];

const WEIGH_METHODS = ['สถานีตรวจสอบน้ำหนัก', 'เครื่องชั่งน้ำหนักเคลื่อนที่ (Spot Check)', 'ชั่งที่โรงงาน/ต้นทาง'];

const ACTIONS = [
  'เปรียบเทียบปรับ',
  'ส่งพนักงานสอบสวนดำเนินคดี',
  'สั่งลดน้ำหนัก/ถ่ายสินค้าออก',
  'ตักเตือน',
];

export const OverweightForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { users, charges } = useStationData({ charges: true });

  const blank: Record<string, string> = {
    reportDateTime: getNowDateTimeLocal(),
    inspectorName: '',
    plateNumber: '',
    plateProvince: '',
    vehicleType: '',
    axleCount: '',
    driverName: '',
    company: '',
    cargoType: '',
    actualWeight: '',
    legalWeight: '',
    location: '',
    lat: '',
    lng: '',
    weighMethod: '',
    action: '',
    charge: '',
    caseNumber: '',
    remark: '',
  };
  const [f, setF, draft] = useFormDraft('overweight', blank, user?.username);
  const [files, setFiles] = useState<FileList | null>(null);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  const resetForm = () => {
    draft.clear();
    setF({ ...blank, reportDateTime: getNowDateTimeLocal() });
  };

  /** เลือกจำนวนเพลาแล้วเติมพิกัดให้ แต่ไม่ทับค่าที่เจ้าหน้าที่พิมพ์เองไว้แล้ว */
  const setAxle = (value: string) => {
    setF((p) => ({
      ...p,
      axleCount: value,
      legalWeight: p.legalWeight || LEGAL_WEIGHT_BY_AXLE[value] || '',
    }));
  };

  const actual = parseInt(f.actualWeight) || 0;
  const legal = parseInt(f.legalWeight) || 0;
  const excess = Math.max(0, actual - legal);
  const percent = legal > 0 ? Math.round((excess * 10000) / legal) / 100 : 0;

  const submit = async () => {
    const required = ['inspectorName', 'plateNumber', 'vehicleType', 'actualWeight', 'legalWeight', 'location'];
    if (required.some((k) => !f[k])) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลที่มีเครื่องหมาย * ให้ครบถ้วน', 'warning');
      return;
    }
    if (actual <= 0 || legal <= 0) {
      Swal.fire('น้ำหนักไม่ถูกต้อง', 'น้ำหนักที่ชั่งได้และพิกัดตามกฎหมายต้องมากกว่า 0', 'warning');
      return;
    }

    const overText = excess > 0 ? `เกินพิกัด ${excess.toLocaleString()} กก. (${percent}%)` : 'ไม่เกินพิกัด';
    const previewText =
      `เรียน ผู้บังคับบัญชา\nรายงานการตรวจสอบรถบรรทุกน้ำหนักเกิน\n` +
      `วันที่ ${formatPreviewDate(f.reportDateTime)}\n\n` +
      `ผู้ตรวจ ${f.inspectorName}\nทะเบียนรถ ${f.plateNumber} ${f.plateProvince}\n` +
      `ประเภทรถ ${f.vehicleType} จำนวน ${f.axleCount || '-'} เพลา\n` +
      `ผู้ขับขี่ ${f.driverName || '-'}\nผู้ประกอบการ ${f.company || '-'}\n` +
      `สินค้าที่บรรทุก ${f.cargoType || '-'}\n\n` +
      `น้ำหนักที่ชั่งได้ ${actual.toLocaleString()} กก.\nพิกัดตามกฎหมาย ${legal.toLocaleString()} กก.\n${overText}\n\n` +
      `สถานที่ตรวจ ${f.location}\nวิธีการชั่ง ${f.weighMethod || '-'}\n` +
      `ผลการดำเนินการ ${f.action || '-'}\nข้อหา ${f.charge || '-'}\n\nจึงเรียนมาเพื่อโปรดทราบ`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;

    loadingModal('กำลังบันทึกรายงาน...');
    const payload = { ...f, unitId: user?.unit, stationId: user?.station, actionBy: user?.username };
    const res = await api.submitReport('overweight', payload, user?.token, { files: await filesToBase64(files) });
    if (res.status === 'success') {
      draft.clear();
      await showLineCopyResult(res.message || 'บันทึกรายงานเรียบร้อย', res.lineText || previewText, copied ? previewText : undefined);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="รายงานการตรวจสอบรถบรรทุกน้ำหนักเกิน" onBack={onBack} maxWidth={900}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #fd7e14' }}>
        {draft.restored && <DraftNotice onClear={resetForm} />}
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วันที่เวลาที่ตรวจ</label>
            <div className="d-flex gap-2 align-items-stretch">
              <ThaiDateInput type="datetime-local" value={f.reportDateTime} onChange={(v) => set('reportDateTime', v)} />
              <button type="button" className="btn btn-outline-warning" onClick={() => set('reportDateTime', getNowDateTimeLocal())}>
                <i className="fa-solid fa-clock-rotate-left"></i>
              </button>
            </div>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">ผู้ตรวจ *</label>
            <select className="form-select" value={f.inspectorName} onChange={(e) => set('inspectorName', e.target.value)}>
              <option value="">-- เลือกรายชื่อ --</option>
              {users.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>

          <div className="col-12"><hr className="border-secondary" /><span className="badge bg-warning text-dark">ข้อมูลรถ</span></div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">ทะเบียนรถ *</label>
            <input type="text" className="form-control" placeholder="เช่น 70-1234" value={f.plateNumber} onChange={(e) => set('plateNumber', e.target.value)} />
          </div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">จังหวัดทะเบียน</label>
            <input type="text" className="form-control" placeholder="เช่น ตาก" value={f.plateProvince} onChange={(e) => set('plateProvince', e.target.value)} />
          </div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">ประเภทรถ *</label>
            <select className="form-select" value={f.vehicleType} onChange={(e) => set('vehicleType', e.target.value)}>
              <option value="">-- เลือกประเภท --</option>
              {VEHICLE_TYPES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div className="col-6 col-md-3">
            <label className="form-label small text-white-50">จำนวนเพลา</label>
            <select className="form-select" value={f.axleCount} onChange={(e) => setAxle(e.target.value)}>
              <option value="">-- เลือก --</option>
              {Object.keys(LEGAL_WEIGHT_BY_AXLE).map((a) => <option key={a} value={a}>{a} เพลา</option>)}
            </select>
          </div>
          <div className="col-6 col-md-4">
            <label className="form-label small text-white-50">ชื่อผู้ขับขี่</label>
            <input type="text" className="form-control" value={f.driverName} onChange={(e) => set('driverName', e.target.value)} />
          </div>
          <div className="col-12 col-md-5">
            <label className="form-label small text-white-50">บริษัท / ผู้ประกอบการ</label>
            <input type="text" className="form-control" value={f.company} onChange={(e) => set('company', e.target.value)} />
          </div>
          <div className="col-12">
            <label className="form-label small text-white-50">ประเภทสินค้าที่บรรทุก</label>
            <input type="text" className="form-control" placeholder="เช่น หิน ดิน ทราย / สินค้าเกษตร" value={f.cargoType} onChange={(e) => set('cargoType', e.target.value)} />
          </div>

          <div className="col-12"><hr className="border-secondary" /><span className="badge bg-danger">การชั่งน้ำหนัก</span></div>
          <div className="col-6 col-md-4">
            <label className="form-label small text-white-50">น้ำหนักที่ชั่งได้ (กก.) *</label>
            <input type="number" className="form-control text-center border-danger" min="0" value={f.actualWeight} onChange={(e) => set('actualWeight', e.target.value)} />
          </div>
          <div className="col-6 col-md-4">
            <label className="form-label small text-white-50">พิกัดตามกฎหมาย (กก.) *</label>
            <input type="number" className="form-control text-center" min="0" value={f.legalWeight} onChange={(e) => set('legalWeight', e.target.value)} />
            <p className="text-white-50 mb-0" style={{ fontSize: '0.7rem' }}>* เติมให้อัตโนมัติเมื่อเลือกจำนวนเพลา แก้ทับได้</p>
          </div>
          <div className="col-12 col-md-4">
            <label className="form-label small text-white-50">น้ำหนักส่วนเกิน</label>
            <div className={`form-control text-center fw-bold ${excess > 0 ? 'text-danger' : 'text-success'}`} style={{ background: 'rgba(0,0,0,0.3)' }}>
              {excess > 0 ? `${excess.toLocaleString()} กก. (${percent}%)` : 'ไม่เกินพิกัด'}
            </div>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วิธีการชั่ง</label>
            <select className="form-select" value={f.weighMethod} onChange={(e) => set('weighMethod', e.target.value)}>
              <option value="">-- เลือกวิธี --</option>
              {WEIGH_METHODS.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>

          <div className="col-12"><hr className="border-secondary" /><span className="badge bg-info">สถานที่และการดำเนินการ</span></div>
          <div className="col-12">
            <label className="form-label small text-white-50">สถานที่ตรวจ *</label>
            <input type="text" className="form-control" placeholder="เช่น ทล.1 กม.571 ต.วังจันทร์ อ.สามเงา จ.ตาก" value={f.location} onChange={(e) => set('location', e.target.value)} />
          </div>
          <div className="col-12 col-md-5">
            <label className="form-label small text-white-50">ละติจูด</label>
            <input type="text" className="form-control" value={f.lat} onChange={(e) => set('lat', e.target.value)} />
          </div>
          <div className="col-12 col-md-5">
            <label className="form-label small text-white-50">ลองจิจูด</label>
            <input type="text" className="form-control" value={f.lng} onChange={(e) => set('lng', e.target.value)} />
          </div>
          <div className="col-12 col-md-2 d-flex align-items-end">
            <LocationPickerButton
              lat={f.lat}
              lng={f.lng}
              title="ปักหมุดจุดตรวจน้ำหนัก"
              label="ปักหมุด"
              onSelect={(lat, lng) => setF((p) => ({ ...p, lat, lng }))}
            />
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">ผลการดำเนินการ</label>
            <select className="form-select" value={f.action} onChange={(e) => set('action', e.target.value)}>
              <option value="">-- เลือกผลการดำเนินการ --</option>
              {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">ข้อหา</label>
            <input className="form-control" list="owt-charges" placeholder="เลือกหรือพิมพ์ข้อหา" value={f.charge} onChange={(e) => set('charge', e.target.value)} />
            <datalist id="owt-charges">
              {charges.map((c) => <option key={c} value={c} />)}
            </datalist>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">เลขที่ใบสั่ง / เลขคดี</label>
            <input type="text" className="form-control" value={f.caseNumber} onChange={(e) => set('caseNumber', e.target.value)} />
          </div>
          <div className="col-12">
            <label className="form-label small text-white-50">หมายเหตุ</label>
            <textarea className="form-control" rows={2} value={f.remark} onChange={(e) => set('remark', e.target.value)} />
          </div>

          <div className="col-12">
            <label className="form-label small text-white-50">แนบภาพ (ใบชั่ง / ทะเบียนรถ / สินค้า)</label>
            <input type="file" className="form-control" multiple accept="image/*,.pdf" onChange={(e) => setFiles(e.target.files)} />
          </div>

          <div className="col-12 mt-4">
            <button type="button" className="btn btn-warning w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={submit}>
              <i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง
            </button>
          </div>
        </div>
      </div>
    </FormShell>
  );
};

export default OverweightForm;
