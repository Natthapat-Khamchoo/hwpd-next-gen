import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { ShieldCheck, ArrowLeft, CheckCircle2, XCircle } from 'lucide-react';
import Swal from 'sweetalert2';

interface StationAdminDashboardProps {
  onBack: () => void;
}

export const StationAdminDashboard: React.FC<StationAdminDashboardProps> = ({ onBack }) => {
  const { user } = useAuth();

  const [pendingItems, setPendingItems] = useState([
    { recordId: 'ARR-260722-1400-101', type: 'รายงานจับกุม (พ.ร.บ.ยาเสพติดฯ)', date: '22/07/2569 14:00', reporter: 'ด.ต. สมชาย สายตรวจ', unit: 'หน่วยฯดอนจาน', details: 'ของกลาง ยาบ้า 200 เม็ด ผู้ต้องหา 1 คน' },
    { recordId: 'ARR-260722-1130-204', type: 'รายงานจับกุม (พ.ร.บ.จราจรทางบก)', date: '22/07/2569 11:30', reporter: 'ส.ต.อ. รักชาติ มั่นคง', unit: 'หน่วยฯจอมทอง', details: 'เมาแล้วขับ วัดปริมาณแอลกอฮอล์ได้ 120 mg%' },
  ]);

  const handleApprove = (recordId: string) => {
    Swal.fire({
      title: 'ยืนยันการอนุมัติรายงาน?',
      text: `ต้องการอนุมัติรายการ ${recordId} เข้าสู่ฐานข้อมูลหลักใช่หรือไม่`,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'อนุมัติ',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#10b981',
    }).then((res) => {
      if (res.isConfirmed) {
        setPendingItems(pendingItems.filter((i) => i.recordId !== recordId));
        Swal.fire('สำเร็จ', 'อนุมัติรายการเรียบร้อยแล้ว', 'success');
      }
    });
  };

  const handleReject = (recordId: string) => {
    Swal.fire({
      title: 'ระบุเหตุผลการตีกลับ/ยกเลิก',
      input: 'text',
      inputPlaceholder: 'กรอกเหตุผล...',
      showCancelButton: true,
      confirmButtonText: 'ส่งคืน',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#ef4444',
    }).then((res) => {
      if (res.isConfirmed && res.value) {
        setPendingItems(pendingItems.filter((i) => i.recordId !== recordId));
        Swal.fire('ส่งคืนแล้ว', `ตีกลับรายการ ${recordId} เรียบร้อยแล้ว`, 'info');
      }
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>ย้อนกลับเมนูหลัก</span>
        </button>

        <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>แดชบอร์ดสิบเวร / เจ้าหน้าที่ตรวจรายงาน</span>
        </div>
      </div>

      <div className="glass-card p-6 md:p-8 space-y-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
              <span>รายการรอตรวจอนุมัติ (สิบเวรประจำสถานี)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              สังกัด {user?.unit} (ส.ทล.{user?.station} กก.{user?.station ? user?.station[0] : '5'})
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">คงเหลือรอตรวจสอบ:</span>
            <span className="px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 font-bold text-sm border border-amber-500/30">
              {pendingItems.length} รายการ
            </span>
          </div>
        </div>

        {pendingItems.length === 0 ? (
          <div className="text-center py-12 text-slate-400 space-y-2">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto opacity-80" />
            <p className="font-semibold text-white">ไม่มีรายการค้างตรวจอนุมัติในขณะนี้</p>
            <p className="text-xs text-slate-500">รายงานที่เจ้าหน้าที่ส่งเข้ามาใหม่จะปรากฏที่นี่โดยอัตโนมัติ</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-white/5 text-slate-400 uppercase tracking-wider font-semibold border-b border-white/10">
                <tr>
                  <th className="p-3">รหัสอ้างอิง</th>
                  <th className="p-3">ประเภทรายงาน</th>
                  <th className="p-3">ผู้ส่ง / หน่วยงาน</th>
                  <th className="p-3">รายละเอียดสรุป</th>
                  <th className="p-3 text-center">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {pendingItems.map((item) => (
                  <tr key={item.recordId} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 font-mono text-cyan-400 font-semibold">{item.recordId}</td>
                    <td className="p-3 font-medium text-white">{item.type}</td>
                    <td className="p-3">
                      <div className="text-white font-medium">{item.reporter}</div>
                      <div className="text-[11px] text-slate-400">{item.unit} ({item.date})</div>
                    </td>
                    <td className="p-3 text-slate-300 max-w-xs truncate">{item.details}</td>
                    <td className="p-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleApprove(item.recordId)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30 font-semibold flex items-center gap-1 transition-all"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> อนุมัติ
                        </button>
                        <button
                          onClick={() => handleReject(item.recordId)}
                          className="px-3 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30 font-semibold flex items-center gap-1 transition-all"
                        >
                          <XCircle className="w-3.5 h-3.5" /> ตีกลับ
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
