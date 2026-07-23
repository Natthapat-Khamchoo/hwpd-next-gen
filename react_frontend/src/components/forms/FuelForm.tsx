import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import { getNowDateTimeLocal, loadingModal } from '../../utils/formHelpers';
import Swal from 'sweetalert2';

export const FuelForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { users } = useStationData();
  const [tab, setTab] = useState<'refuel' | 'oil'>('refuel');

  const [refuel, setRefuel] = useState<Record<string, string>>({
    actionDateTime: getNowDateTimeLocal(), actionPerson: '', plateNumber: '', currentMileage: '', fuelType: '', liters: '', totalPrice: '', receiptNumber: '',
  });
  const [oil, setOil] = useState<Record<string, string>>({
    actionDateTime: getNowDateTimeLocal(), actionPerson: '', plateNumber: '', carType: '', liters: '', prevMileage: '', currentMileage: '',
  });
  const rset = (k: string, v: string) => setRefuel((p) => ({ ...p, [k]: v }));
  const oset = (k: string, v: string) => setOil((p) => ({ ...p, [k]: v }));
  const distanceUsed = (() => {
    const prev = parseFloat(oil.prevMileage) || 0;
    const curr = parseFloat(oil.currentMileage) || 0;
    if (prev > 0 && curr > 0) return Math.max(0, curr - prev);
    return '';
  })();

  const submitFuel = async (type: 'refuel' | 'oil') => {
    const data = type === 'refuel' ? refuel : oil;
    const required = type === 'refuel'
      ? ['actionPerson', 'plateNumber', 'currentMileage', 'fuelType', 'liters', 'totalPrice', 'receiptNumber']
      : ['actionPerson', 'plateNumber', 'carType', 'liters', 'prevMileage', 'currentMileage'];
    if (required.some((k) => !data[k])) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลให้ครบถ้วน', 'warning');
      return;
    }
    loadingModal('กำลังบันทึกข้อมูล...');
    const payload: Record<string, any> = {
      ...data,
      unitId: user?.unit,
      stationId: user?.station,
      actionBy: user?.username,
      recordType: type === 'refuel' ? 'เติมน้ำมัน' : 'เปลี่ยนน้ำมันเครื่อง',
    };
    if (type === 'oil') payload.distanceUsed = distanceUsed;
    const res = await api.submitReport('fuel', payload, user?.token);
    if (res.status === 'success') {
      await Swal.fire('สำเร็จ!', 'บันทึกข้อมูลลงระบบเรียบร้อย', 'success');
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="น้ำมัน / น้ำมันเครื่อง" onBack={onBack}>
      <ul className="nav nav-pills mb-4 justify-content-center">
        <li className="nav-item">
          <button className={`nav-link ${tab === 'refuel' ? 'active' : ''}`} onClick={() => setTab('refuel')}>
            <i className="fa-solid fa-gas-pump"></i> 1. เติมน้ำมัน
          </button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${tab === 'oil' ? 'active' : ''}`} onClick={() => setTab('oil')}>
            <i className="fa-solid fa-oil-can"></i> 2. เปลี่ยนน้ำมันเครื่อง
          </button>
        </li>
      </ul>

      {tab === 'refuel' && (
        <div className="glass-card w-100">
          <h5 className="text-center text-warning mb-4">บันทึกการเติมน้ำมันเชื้อเพลิง</h5>
          <div className="row g-3">
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันเวลาที่เติมน้ำมัน</label>
              <div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={refuel.actionDateTime} onChange={(e) => rset('actionDateTime', e.target.value)} /><button type="button" className="btn btn-outline-warning" onClick={() => rset('actionDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div>
            </div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ผู้เติมน้ำมัน</label>
              <select className="form-select border-warning" value={refuel.actionPerson} onChange={(e) => rset('actionPerson', e.target.value)}><option value="">-- เลือกรายชื่อ --</option>{users.map((u) => <option key={u} value={u}>{u}</option>)}</select>
            </div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">หมายเลขทะเบียนรถ</label><input type="text" className="form-control" placeholder="เช่น กท 1234" value={refuel.plateNumber} onChange={(e) => rset('plateNumber', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">เลขไมล์รถ (ขณะเติม)</label><input type="number" className="form-control" placeholder="เช่น 150000" value={refuel.currentMileage} onChange={(e) => rset('currentMileage', e.target.value)} /></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">ประเภทน้ำมัน</label>
              <select className="form-select" value={refuel.fuelType} onChange={(e) => rset('fuelType', e.target.value)}><option value="">-- เลือกประเภท --</option><option value="ดีเซล">ดีเซล</option><option value="แก๊สโซฮอล์ 91">แก๊สโซฮอล์ 91</option><option value="แก๊สโซฮอล์ 95">แก๊สโซฮอล์ 95</option></select>
            </div>
            <div className="col-md-4 col-6"><label className="form-label small text-white-50">จำนวน (ลิตร)</label><input type="number" step="0.001" className="form-control text-center" placeholder="0.000" value={refuel.liters} onChange={(e) => rset('liters', e.target.value)} /></div>
            <div className="col-md-4 col-6"><label className="form-label small text-white-50">ราคา (บาท)</label><input type="number" step="0.01" className="form-control text-center border-success" placeholder="0.00" value={refuel.totalPrice} onChange={(e) => rset('totalPrice', e.target.value)} /></div>
            <div className="col-12"><label className="form-label small text-white-50">เลขที่ใบเสร็จ</label><input type="text" className="form-control" placeholder="กรอกเลขที่ใบเสร็จรับเงิน" value={refuel.receiptNumber} onChange={(e) => rset('receiptNumber', e.target.value)} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn btn-warning w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={() => submitFuel('refuel')}><i className="fa-solid fa-floppy-disk"></i> บันทึกข้อมูลเติมน้ำมัน</button></div>
          </div>
        </div>
      )}

      {tab === 'oil' && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">บันทึกเปลี่ยนน้ำมันเครื่อง</h5>
          <div className="row g-3">
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันเวลาที่เปลี่ยนน้ำมันเครื่อง</label>
              <div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={oil.actionDateTime} onChange={(e) => oset('actionDateTime', e.target.value)} /><button type="button" className="btn btn-outline-info" onClick={() => oset('actionDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div>
            </div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ผู้เปลี่ยนน้ำมันเครื่อง</label>
              <select className="form-select border-info" value={oil.actionPerson} onChange={(e) => oset('actionPerson', e.target.value)}><option value="">-- เลือกรายชื่อ --</option>{users.map((u) => <option key={u} value={u}>{u}</option>)}</select>
            </div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">หมายเลขทะเบียนรถ</label><input type="text" className="form-control" placeholder="เช่น กท 1234" value={oil.plateNumber} onChange={(e) => oset('plateNumber', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ประเภทรถ</label>
              <select className="form-select" value={oil.carType} onChange={(e) => oset('carType', e.target.value)}><option value="">-- เลือกประเภท --</option><option value="รถเก๋ง">รถเก๋ง</option><option value="รถกระบะ">รถกระบะ</option></select>
            </div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12"><label className="form-label small text-white-50">จำนวนน้ำมันเครื่อง (ลิตร)</label><input type="number" step="0.01" className="form-control" placeholder="ระบุจำนวนลิตร" value={oil.liters} onChange={(e) => oset('liters', e.target.value)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เลขไมล์ครั้งก่อน</label><input type="number" className="form-control" placeholder="เช่น 140000" value={oil.prevMileage} onChange={(e) => oset('prevMileage', e.target.value)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เลขไมล์ปัจจุบัน</label><input type="number" className="form-control border-info" placeholder="เช่น 150000" value={oil.currentMileage} onChange={(e) => oset('currentMileage', e.target.value)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">ระยะทางที่ใช้งาน (กม.)</label><input type="number" className="form-control bg-dark text-warning fw-bold" readOnly placeholder="คำนวณอัตโนมัติ" value={distanceUsed} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn btn-info w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={() => submitFuel('oil')}><i className="fa-solid fa-floppy-disk"></i> บันทึกข้อมูลเปลี่ยนน้ำมันเครื่อง</button></div>
          </div>
        </div>
      )}
    </FormShell>
  );
};
