import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { ShieldCheck, ArrowLeft, Send } from 'lucide-react';
import Swal from 'sweetalert2';

interface CheckpointFormProps {
  onBack: () => void;
}

export const CheckpointForm: React.FC<CheckpointFormProps> = ({ onBack }) => {
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const today = new Date().toISOString().split('T')[0];
  const [formData, setFormData] = useState({
    reportDateTime: `${today}T10:00`,
    stationId: user?.station || '51',
    unitId: user?.unit || 'หน่วยฯดอนจาน',
    dutyOfficer: user?.fullName || '',
    totalPersonnel: 4,
    carNumber: '5101',
    location: 'ทางหลวงหมายเลข 12 กม. 45+000 ต.ดอนจาน อ.ดอนจาน จ.กาฬสินธุ์',
    actionBy: user?.fullName || 'เจ้าหน้าที่',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await api.submitReport('checkpoint', formData, user?.token);
      if (res.status === 'success') {
        Swal.fire({
          icon: 'success',
          title: 'บันทึกจุดตรวจ ว.43 สำเร็จ',
          text: `รหัสอ้างอิง: ${res.recordId || 'CHK-SUCCESS'}`,
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
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>ย้อนกลับเมนูหลัก</span>
        </button>

        <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>ฟอร์ม CHK (ตั้งด่าน/จุดตรวจ)</span>
        </div>
      </div>

      <div className="glass-card p-6 md:p-8 space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-purple-400" />
            <span>รายงานการตั้งจุดตรวจ ว.43 (อาญา/จราจร)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            สังกัด {formData.unitId} (ส.ทล.{formData.stationId} กก.{formData.stationId[0]} บก.ทล.)
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="form-label">วันเวลาที่ตั้งด่าน</label>
              <input
                type="datetime-local"
                className="form-input"
                value={formData.reportDateTime}
                onChange={(e) => setFormData({ ...formData, reportDateTime: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="form-label">รถวิทยุประจำจุดตรวจ</label>
              <input
                type="text"
                className="form-input"
                value={formData.carNumber}
                onChange={(e) => setFormData({ ...formData, carNumber: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="form-label">หัวหน้าชุดควบคุมการปฏิบัติ</label>
              <input
                type="text"
                className="form-input"
                value={formData.dutyOfficer}
                onChange={(e) => setFormData({ ...formData, dutyOfficer: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="form-label">จำนวนกำลังพลรวม (นาย)</label>
              <input
                type="number"
                min="1"
                className="form-input"
                value={formData.totalPersonnel}
                onChange={(e) => setFormData({ ...formData, totalPersonnel: parseInt(e.target.value) || 1 })}
                required
              />
            </div>
          </div>

          <div>
            <label className="form-label">สถานที่ตั้งจุดตรวจ / พิกัดทางหลวง</label>
            <textarea
              rows={3}
              className="form-textarea"
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              required
            ></textarea>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={onBack} className="px-5 py-2.5 rounded-xl border border-white/20 text-slate-300 hover:bg-white/5 text-sm">
              ยกเลิก
            </button>
            <button type="submit" disabled={submitting} className="btn-neon-purple px-6 py-2.5 text-sm">
              {submitting ? 'กำลังบันทึก...' : (
                <span className="flex items-center gap-2">
                  <Send className="w-4 h-4" />
                  ส่งรายงานตั้งด่าน
                </span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
