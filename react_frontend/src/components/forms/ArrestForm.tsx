import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { ShieldAlert, ArrowLeft, Send, Plus, Trash2, UserCheck } from 'lucide-react';
import Swal from 'sweetalert2';

interface ArrestFormProps {
  onBack: () => void;
}

export const ArrestForm: React.FC<ArrestFormProps> = ({ onBack }) => {
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const today = new Date().toISOString().split('T')[0];
  const [formData, setFormData] = useState({
    reportDateTime: `${today}T14:30`,
    actionDateTime: `${today}T14:00`,
    stationId: user?.station || '51',
    unitId: user?.unit || 'หน่วยฯดอนจาน',
    category: 'พ.ร.บ.ยาเสพติดฯ',
    arrestBy: 'ส.ทล.1 กก.5 บก.ทล.',
    arrestType: 'จับกุมซึ่งหน้า',
    warrantType: 'ไม่มีหมายจับ',
    location: 'บริเวณ กม. 12+500 ทล.12 ต.ดอนจาน อ.ดอนจาน จ.กาฬสินธุ์',
    lat: '16.4321',
    lng: '103.5123',
    items: 'ยาบ้า (เมทแอมเฟตามีน) จำนวน 200 เม็ด',
    circumstances: 'ขณะตรวจเขตพบรถจักรยานยนต์ต้องสงสัยขับขี่มีท่าทางลุกลี้ลุกลน จึงเรียกตรวจค้นพบของกลางซุกซ่อนในกระเป๋าเสื้อ',
    forwarding: 'นำส่ง พนักงานสอบสวน สภ.ดอนจาน เพื่อดำเนินคดีตามกฎหมายต่อไป',
    actionBy: user?.fullName || 'เจ้าหน้าที่',
  });

  const [team, setTeam] = useState<string[]>([user?.fullName || 'ด.ต. สมชาย สายตรวจ', 'ส.ต.อ. รักชาติ มั่นคง']);
  const [newTeamMember, setNewTeamMember] = useState('');

  const [suspects] = useState([
    { name: 'นาย สมศักดิ์ มีดี', idCard: '1459900123456', nat: 'ไทย', age: '35', address: '123 ม.1 ต.ดอนจาน อ.ดอนจาน จ.กาฬสินธุ์' }
  ]);

  const [charges, setCharges] = useState<string[]>([
    'มียาเสพติดให้โทษประเภท 1 (เมทแอมเฟตามีน) ไว้ในครอบครองเพื่อการค้าโดยไม่ได้รับอนุญาต'
  ]);
  const [newCharge, setNewCharge] = useState('');

  const addTeamMember = () => {
    if (newTeamMember.trim()) {
      setTeam([...team, newTeamMember.trim()]);
      setNewTeamMember('');
    }
  };

  const removeTeamMember = (idx: number) => {
    setTeam(team.filter((_, i) => i !== idx));
  };

  const addCharge = () => {
    if (newCharge.trim()) {
      setCharges([...charges, newCharge.trim()]);
      setNewCharge('');
    }
  };

  const removeCharge = (idx: number) => {
    setCharges(charges.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        formData,
        teamArray: team,
        suspectArray: suspects,
        chargeArray: charges,
      };
      const res = await api.submitReport('arrest', payload, user?.token);
      if (res.status === 'success') {
        Swal.fire({
          icon: 'success',
          title: 'บันทึกรายงานการจับกุมสำเร็จ',
          text: `รหัสอ้างอิง: ${res.recordId || 'ARR-SUCCESS'} (รอการตรวจสอบสิบเวร)`,
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

        <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>ฟอร์ม ARR (รายงานการจับกุม)</span>
        </div>
      </div>

      <div className="glass-card p-6 md:p-8 space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-rose-400" />
            <span>รายงานผลการจับกุมผู้ต้องหา & ของกลาง</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            สังกัด {formData.unitId} (ส.ทล.{formData.stationId} กก.{formData.stationId[0]} บก.ทล.)
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-rose-300 border-b border-white/10 pb-2">
              1. ประเภทคดีและวันเวลาจับกุม
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="form-label">ประเภทคดีหลัก</label>
                <select
                  className="form-select"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  <option value="พ.ร.บ.ยาเสพติดฯ">พ.ร.บ.ยาเสพติดฯ</option>
                  <option value="พ.ร.บ.อาวุธปืนฯ">พ.ร.บ.อาวุธปืนฯ</option>
                  <option value="พ.ร.บ.จราจรทางบก">พ.ร.บ.จราจรทางบก</option>
                  <option value="พ.ร.บ.ทางหลวง">พ.ร.บ.ทางหลวง</option>
                  <option value="คดีอาญาอื่นๆ">คดีอาญาอื่นๆ</option>
                </select>
              </div>
              <div>
                <label className="form-label">วันเวลาที่เกิดเหตุ/จับกุม</label>
                <input
                  type="datetime-local"
                  className="form-input"
                  value={formData.actionDateTime}
                  onChange={(e) => setFormData({ ...formData, actionDateTime: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label">ประเภทการจับกุม</label>
                <select
                  className="form-select"
                  value={formData.arrestType}
                  onChange={(e) => setFormData({ ...formData, arrestType: e.target.value })}
                >
                  <option value="จับกุมซึ่งหน้า">จับกุมซึ่งหน้า</option>
                  <option value="จับตามหมายจับ">จับตามหมายจับ</option>
                  <option value="ขยายผลจับกุม">ขยายผลจับกุม</option>
                </select>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-cyan-300 border-b border-white/10 pb-2">
              2. รายชื่อเจ้าหน้าที่ชุดจับกุม
            </h3>

            <div className="flex flex-wrap gap-2">
              {team.map((member, idx) => (
                <span key={idx} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-xs">
                  <UserCheck className="w-3.5 h-3.5" />
                  {member}
                  <button type="button" onClick={() => removeTeamMember(idx)} className="hover:text-rose-400 ml-1">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                className="form-input text-xs"
                placeholder="เพิ่ม ยศ ชื่อ สกุล เจ้าหน้าที่ชุดจับกุม"
                value={newTeamMember}
                onChange={(e) => setNewTeamMember(e.target.value)}
              />
              <button type="button" onClick={addTeamMember} className="btn-neon text-xs py-2 px-4 shrink-0">
                <Plus className="w-4 h-4" /> เพิ่ม
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-amber-300 border-b border-white/10 pb-2">
              3. ข้อกล่าวหาและของกลาง
            </h3>

            <div>
              <label className="form-label">รายการข้อกล่าวหา</label>
              <div className="space-y-2 mb-2">
                {charges.map((c, i) => (
                  <div key={i} className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-white/10 text-xs text-white">
                    <span>{i + 1}. {c}</span>
                    <button type="button" onClick={() => removeCharge(i)} className="text-rose-400 hover:text-rose-300">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  className="form-input text-xs"
                  placeholder="เพิ่มข้อกล่าวหา"
                  value={newCharge}
                  onChange={(e) => setNewCharge(e.target.value)}
                />
                <button type="button" onClick={addCharge} className="btn-neon-gold text-xs py-2 px-4 shrink-0">
                  <Plus className="w-4 h-4" /> เพิ่มข้อหา
                </button>
              </div>
            </div>

            <div>
              <label className="form-label">รายการของกลางที่ตรวจยึด</label>
              <textarea
                rows={2}
                className="form-textarea"
                value={formData.items}
                onChange={(e) => setFormData({ ...formData, items: e.target.value })}
              ></textarea>
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={onBack} className="px-5 py-2.5 rounded-xl border border-white/20 text-slate-300 hover:bg-white/5 text-sm">
              ยกเลิก
            </button>
            <button type="submit" disabled={submitting} className="btn-neon-purple px-6 py-2.5 text-sm">
              {submitting ? 'กำลังบันทึก...' : (
                <span className="flex items-center gap-2">
                  <Send className="w-4 h-4" />
                  ส่งรายงานจับกุม
                </span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
