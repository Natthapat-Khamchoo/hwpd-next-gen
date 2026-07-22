import React, { useState } from 'react';
import { Award, ArrowLeft, Search, TrendingUp, ShieldAlert, ShieldCheck, AlertTriangle, Users, Crown, Building } from 'lucide-react';

interface SuperCommanderDashboardProps {
  onBack: () => void;
}

export const SuperCommanderDashboard: React.FC<SuperCommanderDashboardProps> = ({ onBack }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const kpis = [
    { title: 'จับกุมรวมทั่วประเทศ', val: '1,248', icon: ShieldAlert, color: 'from-rose-500 to-red-600', text: 'text-rose-400' },
    { title: 'ตั้งจุดตรวจ ว.43', val: '3,850', icon: ShieldCheck, color: 'from-purple-500 to-indigo-600', text: 'text-purple-400' },
    { title: 'อุบัติเหตุทางหลวง', val: '412', icon: AlertTriangle, color: 'from-amber-500 to-yellow-600', text: 'text-amber-400' },
    { title: 'บริการผู้เดินทาง', val: '8,920', icon: Users, color: 'from-cyan-500 to-blue-600', text: 'text-cyan-400' },
    { title: 'ภารกิจ ถปภ. / รับเสด็จ', val: '156', icon: Crown, color: 'from-yellow-400 to-amber-500', text: 'text-yellow-300' },
  ];

  const divisionRankings = [
    { rank: 1, div: 'กก.5 บก.ทล.', arrest: 342, v43: 820, acc: 68, score: 98.5 },
    { rank: 2, div: 'กก.1 บก.ทล.', arrest: 298, v43: 750, acc: 85, score: 94.2 },
    { rank: 3, div: 'กก.2 บก.ทล.', arrest: 210, v43: 610, acc: 54, score: 91.0 },
    { rank: 4, div: 'กก.3 บก.ทล.', arrest: 185, v43: 540, acc: 92, score: 88.4 },
    { rank: 5, div: 'กก.6 บก.ทล.', arrest: 120, v43: 430, acc: 60, score: 84.1 },
  ];

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

        <div className="flex items-center gap-2 text-xs font-bold px-3.5 py-1.5 rounded-full bg-gradient-to-r from-amber-500/20 to-yellow-500/20 text-yellow-300 border border-yellow-500/30">
          <Award className="w-4 h-4" />
          <span>ศูนย์ควบคุมและสั่งการ บก.ทล. (Super Commander Dashboard)</span>
        </div>
      </div>

      <div className="glass-card p-6 md:p-8 bg-gradient-to-r from-yellow-500/10 via-amber-500/5 to-transparent border-yellow-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Award className="w-7 h-7 text-yellow-400" />
            <span>สถิติการปฏิบัติงานภาพรวมระดับประเทศ (บก.ทล.)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            รายงานภาพรวมผลงานรายกองกำกับการ 1-8 และหน่วยบริการทั่วประเทศ
          </p>
        </div>

        <div className="w-full md:w-80 relative">
          <input
            type="text"
            className="form-input text-xs pl-9 pr-4 py-2.5 bg-black/50 border-white/20"
            placeholder="เจาะลึกค้นหาสถิติทั่วประเทศ..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {kpis.map((kpi, i) => {
          const Icon = kpi.icon;
          return (
            <div key={i} className="glass-card p-5 border-white/10 hover:border-white/20 transition-all text-center">
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${kpi.color} flex items-center justify-center mx-auto mb-3 shadow-lg`}>
                <Icon className="w-5 h-5 text-white" />
              </div>
              <div className={`text-2xl font-bold ${kpi.text}`}>{kpi.val}</div>
              <div className="text-[11px] text-slate-400 mt-1">{kpi.title}</div>
            </div>
          );
        })}
      </div>

      <div className="glass-card p-6 md:p-8 space-y-4 border-white/10">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-yellow-400" />
            <span>ตารางจัดอันดับผลงานรายกองกำกับการ (กก.1 - กก.8)</span>
          </h3>
          <span className="text-xs text-slate-400">อัปเดตแบบ Realtime</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-white/5 text-slate-400 uppercase tracking-wider font-semibold border-b border-white/10">
              <tr>
                <th className="p-3 text-center">อันดับ</th>
                <th className="p-3">หน่วยงาน (กองกำกับการ)</th>
                <th className="p-3 text-right">ยอดจับกุม (ราย)</th>
                <th className="p-3 text-right">ตั้งจุดตรวจ ว.43 (ครั้ง)</th>
                <th className="p-3 text-right">อุบัติเหตุ (ครั้ง)</th>
                <th className="p-3 text-right">คะแนนประสิทธิภาพ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {divisionRankings.map((row) => (
                <tr key={row.rank} className="hover:bg-white/5 transition-colors">
                  <td className="p-3 text-center font-bold">
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs ${row.rank === 1 ? 'bg-yellow-500 text-slate-950 font-extrabold' : 'bg-slate-800 text-slate-300'}`}>
                      {row.rank}
                    </span>
                  </td>
                  <td className="p-3 font-semibold text-white flex items-center gap-2">
                    <Building className="w-4 h-4 text-cyan-400" />
                    {row.div}
                  </td>
                  <td className="p-3 text-right font-mono text-rose-400 font-semibold">{row.arrest}</td>
                  <td className="p-3 text-right font-mono text-purple-400 font-semibold">{row.v43}</td>
                  <td className="p-3 text-right font-mono text-amber-400 font-semibold">{row.acc}</td>
                  <td className="p-3 text-right font-mono text-emerald-400 font-bold">{row.score}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
