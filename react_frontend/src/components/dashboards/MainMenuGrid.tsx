import React from 'react';
import { 
  FileText, ShieldCheck, ShieldAlert, AlertTriangle, 
  Megaphone, Crown, Fuel, History, Wrench,
  BarChart3, Users, Building, ChevronRight, Award
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface MainMenuGridProps {
  onSelectView: (viewId: string) => void;
}

export const MainMenuGrid: React.FC<MainMenuGridProps> = ({ onSelectView }) => {
  const { user } = useAuth();
  const role = user?.role || 'Unit_Staff';

  const operationalItems = [
    { id: 'daily', title: 'รายงานประจำวัน', desc: 'OP / กล้อง Body Worn / สถานะประจำวัน', icon: FileText, color: 'from-blue-600 to-cyan-500' },
    { id: 'checkpoint', title: 'รายงานการตั้งด่าน', desc: 'CHK / ตั้งจุดตรวจ ว.43 อาญา/จราจร', icon: ShieldCheck, color: 'from-purple-600 to-indigo-500' },
    { id: 'arrest', title: 'รายงานผลการจับกุม', desc: 'ARR / บันทึกจับกุม ผู้ต้องหา ของกลาง', icon: ShieldAlert, color: 'from-rose-600 to-red-500' },
    { id: 'accident', title: 'รายงานอุบัติเหตุ', desc: 'ACC / เหตุถนนทางหลวง บาดเจ็บ/เสียชีวิต', icon: AlertTriangle, color: 'from-amber-600 to-yellow-500' },
    { id: 'mission', title: 'แจ้งภารกิจปฏิบัติงาน', desc: 'MIS / ลงทะเบียนและปฏิทินภารกิจ', icon: Megaphone, color: 'from-emerald-600 to-teal-500' },
    { id: 'royal_guard', title: 'รายงาน ถปภ. / รับเสด็จ', desc: 'RG / ภารกิจถวายความปลอดภัย VVIP', icon: Crown, color: 'from-yellow-500 to-amber-300', textDark: true },
    { id: 'fuel', title: 'บันทึกน้ำมัน / เครื่องยนต์', desc: 'FUEL / เติมน้ำมันเบิกจ่ายค่าน้ำมันเครื่อง', icon: Fuel, color: 'from-sky-600 to-blue-400' },
    { id: 'history', title: 'ประวัติการส่งรายงาน', desc: 'เรียกดูและตรวจสอบสถานะการอนุมัติ', icon: History, color: 'from-slate-700 to-slate-500' },
    { id: 'tools', title: 'เครื่องมือตำรวจทางหลวง', desc: 'ตรวจสอบกฎหมาย / พิกัดทางหลวง', icon: Wrench, color: 'from-indigo-600 to-violet-500' },
  ];

  const isCommander = role === 'Division_Commander' || role === 'Super_Commander';
  const isAdmin = role === 'Division_Admin' || role === 'Station_Admin' || role === 'สิบเวร' || role === 'HQ_Admin';

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8 animate-fade-in">
      {(isCommander || isAdmin) && (
        <div className="glass-card p-6 border-l-4 border-amber-400 bg-gradient-to-r from-amber-500/10 via-purple-500/5 to-transparent">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                <Award className="w-4 h-4" />
                <span>แดชบอร์ดระดับผู้บังคับบัญชา / บริหารงาน</span>
              </div>
              <h2 className="text-xl font-bold text-white mt-1">
                ระบบรายงานและกำกับการปฏิบัติการ {user?.unit}
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {(role === 'Station_Admin' || role === 'สิบเวร') && (
                <button 
                  onClick={() => onSelectView('station_admin')}
                  className="btn-neon text-sm py-2 px-4"
                >
                  <Users className="w-4 h-4" />
                  แดชบอร์ดสิบเวร (ตรวจอนุมัติงาน)
                </button>
              )}
              {role === 'Division_Admin' && (
                <button 
                  onClick={() => onSelectView('division_admin')}
                  className="btn-neon-purple text-sm py-2 px-4"
                >
                  <Building className="w-4 h-4" />
                  ศูนย์รายงาน กก.5 (ควบคุมงาน)
                </button>
              )}
              {role === 'Division_Commander' && (
                <button 
                  onClick={() => onSelectView('commander')}
                  className="btn-neon-gold text-sm py-2 px-4"
                >
                  <BarChart3 className="w-4 h-4" />
                  แดชบอร์ด ผกก. (สรุปผล กก.)
                </button>
              )}
              {(role === 'Super_Commander' || role === 'HQ_Admin') && (
                <button 
                  onClick={() => onSelectView('super_commander')}
                  className="btn-neon-gold text-sm py-2 px-4"
                >
                  <Award className="w-4 h-4" />
                  ศูนย์ควบคุม บก.ทล. (ภาพรวมประเทศ)
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-lg font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-cyan-400" />
          <span>เมนูบันทึกและส่งรายงานปฏิบัติการ</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {operationalItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className="glass-card glass-card-hover p-5 cursor-pointer flex items-start gap-4 group"
              >
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-tr ${item.color} flex items-center justify-center shadow-lg shrink-0 group-hover:scale-110 transition-transform`}>
                  <Icon className={`w-6 h-6 ${item.textDark ? 'text-slate-950' : 'text-white'}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="font-semibold text-white group-hover:text-cyan-300 transition-colors truncate">
                      {item.title}
                    </h4>
                    <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
                  </div>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    {item.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
