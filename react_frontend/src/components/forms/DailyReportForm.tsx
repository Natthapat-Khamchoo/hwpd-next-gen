import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { FileText, Camera, ArrowLeft, Send } from 'lucide-react';
import Swal from 'sweetalert2';

interface DailyReportFormProps {
  onBack: () => void;
}

export const DailyReportForm: React.FC<DailyReportFormProps> = ({ onBack }) => {
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const today = new Date().toISOString().split('T')[0];
  const [formData, setFormData] = useState({
    reportDateTime: `${today}T08:00`,
    stationId: user?.station || '51',
    unitId: user?.unit || 'หน่วยฯดอนจาน',
    dutyOfficer: user?.fullName || '',
    dutyPhone: '',
    carNumber: '5101',
    driverName: '',
    driverPhone: '',
    radioOpName: '',
    radioOpPhone: '',
    startTime: today,
    endTime: today,
    camTotal: 4,
    camReady: 4,
    camBroken: 0,
    actionBy: user?.fullName || 'เจ้าหน้าที่',
  });

  const handleChange = (field: string, val: any) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await api.submitReport('daily', formData, user?.token);
      if (res.status === 'success') {
        Swal.fire({
          icon: 'success',
          title: 'บันทึกรายงานสำเร็จ',
          text: `รหัสอ้างอิง: ${res.recordId || 'OP-SUCCESS'}`,
        }).then(() => onBack());
      } else {
        Swal.fire('ข้อผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
      }
    } catch (err: any) {
      Swal.fire('เกิดข้อผิดพลาด', err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>ย้อนกลับเมนูหลัก</span>
        </button>

        <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
          <FileText className="w-3.5 h-3.5" />
          <span>ฟอร์ม OP (รายงานประจำวัน)</span>
        </div>
      </div>

      <div className="glass-card p-6 md:p-8 space-y-8">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-6 h-6 text-cyan-400" />
            <span>รายงานปฏิบัติหน้าที่ประจำวัน & สถานะกล้อง Body Worn</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            สังกัด {formData.unitId} (ส.ทล.{formData.stationId} กก.{formData.stationId[0]} บก.ทล.)
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-cyan-300 border-b border-white/10 pb-2">
              1. ข้อมูลกำลังพลและรถวิทยุตรวจเขต
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="form-label">วันเวลาที่รายงาน</label>
                <input
                  type="datetime-local"
                  className="form-input"
                  value={formData.reportDateTime}
                  onChange={(e) => handleChange('reportDateTime', e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="form-label">หมายเลขรถวิทยุตรวจเขต</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.carNumber}
                  onChange={(e) => handleChange('carNumber', e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="form-label">หัวหน้าชุด / ผู้รายงาน</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.dutyOfficer}
                  onChange={(e) => handleChange('dutyOfficer', e.target.value)}
                  placeholder="ยศ ชื่อ สกุล"
                  required
                />
              </div>
              <div>
                <label className="form-label">เบอร์โทรศัพท์หัวหน้าชุด</label>
                <input
                  type="tel"
                  className="form-input"
                  value={formData.dutyPhone}
                  onChange={(e) => handleChange('dutyPhone', e.target.value)}
                  placeholder="08X-XXX-XXXX"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="form-label">พลขับ</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.driverName}
                  onChange={(e) => handleChange('driverName', e.target.value)}
                  placeholder="ยศ ชื่อ สกุล"
                />
              </div>
              <div>
                <label className="form-label">พงว. (พนักงานวิทยุ)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.radioOpName}
                  onChange={(e) => handleChange('radioOpName', e.target.value)}
                  placeholder="ยศ ชื่อ สกุล"
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-purple-300 border-b border-white/10 pb-2 flex items-center gap-1.5">
              <Camera className="w-4 h-4 text-purple-400" />
              <span>2. สถานะการใช้งานกล้องประจำตัว Body Worn</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="form-label">จำนวนกล้องทั้งหมด (ตัว)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input"
                  value={formData.camTotal}
                  onChange={(e) => handleChange('camTotal', parseInt(e.target.value) || 0)}
                />
              </div>
              <div>
                <label className="form-label">พร้อมใช้งาน (ตัว)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input text-emerald-400 font-bold"
                  value={formData.camReady}
                  onChange={(e) => handleChange('camReady', parseInt(e.target.value) || 0)}
                />
              </div>
              <div>
                <label className="form-label">ชำรุด/ใช้ไม่ได้ (ตัว)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input text-rose-400 font-bold"
                  value={formData.camBroken}
                  onChange={(e) => handleChange('camBroken', parseInt(e.target.value) || 0)}
                />
              </div>
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={onBack} className="px-5 py-2.5 rounded-xl border border-white/20 text-slate-300 hover:bg-white/5 text-sm">
              ยกเลิก
            </button>
            <button type="submit" disabled={submitting} className="btn-neon px-6 py-2.5 text-sm">
              {submitting ? (
                <span>กำลังบันทึก...</span>
              ) : (
                <span className="flex items-center gap-2">
                  <Send className="w-4 h-4" />
                  ส่งรายงานประจำวัน
                </span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
