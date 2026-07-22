import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { Shield, Lock, User as UserIcon, LogIn, Sparkles } from 'lucide-react';
import Swal from 'sweetalert2';

export const LoginView: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      Swal.fire('คำเตือน', 'กรุณากรอก Username และ Password', 'warning');
      return;
    }

    setLoading(true);
    try {
      const res = await api.login(username, password);
      if (res.status === 'success' && res.user) {
        login(res.user);
        Swal.fire({
          icon: 'success',
          title: 'เข้าสู่ระบบสำเร็จ',
          text: `ยินดีต้อนรับ ${res.user.fullName}`,
          timer: 1500,
          showConfirmButton: false,
        });
      } else {
        Swal.fire('ข้อผิดพลาด', res.message || 'เข้าสู่ระบบไม่สำเร็จ', 'error');
      }
    } catch (err: any) {
      Swal.fire('เกิดข้อผิดพลาด', err.message || 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md glass-card p-8 relative overflow-hidden shadow-2xl border-white/10 animate-fade-in">
        {/* Glow Ambient Lights */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-cyan-500/20 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-purple-500/20 rounded-full blur-3xl pointer-events-none"></div>

        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-amber-500 to-yellow-300 p-0.5 mx-auto mb-4 shadow-xl shadow-yellow-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
              <Shield className="w-8 h-8 text-yellow-400" />
            </div>
          </div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-yellow-300 via-amber-200 to-white bg-clip-text text-transparent">
            HWPD Next Gen
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            ระบบศูนย์รายงานและบริหารจัดการ กองบังคับการตำรวจทางหลวง
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="form-label flex items-center gap-1.5">
              <UserIcon className="w-4 h-4 text-cyan-400" />
              <span>ชื่อผู้ใช้งาน (Username)</span>
            </label>
            <input
              type="text"
              className="form-input"
              placeholder="ระบุชื่อผู้ใช้งาน"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div>
            <label className="form-label flex items-center gap-1.5">
              <Lock className="w-4 h-4 text-purple-400" />
              <span>รหัสผ่าน (Password)</span>
            </label>
            <input
              type="password"
              className="form-input"
              placeholder="ระบุรหัสผ่าน"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-neon py-3 mt-2 text-base font-semibold"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                กำลังตรวจสอบ...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <LogIn className="w-5 h-5" />
                เข้าสู่ระบบ
              </span>
            )}
          </button>
        </form>

        {/* Quick Demo Login Buttons */}
        <div className="mt-8 pt-6 border-t border-white/10 text-center">
          <div className="flex items-center justify-center gap-1 text-xs text-amber-400 font-medium mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>ทางลัดทดลองเข้าใช้งาน (Demo Mode)</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            <button
              onClick={() => handleQuickLogin('officer51', 'password123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border border-blue-500/20 transition-all"
            >
              เจ้าหน้าที่ (กก.5)
            </button>
            <button
              onClick={() => handleQuickLogin('admin50', 'password123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/20 transition-all"
            >
              ศูนย์รายงาน (กก.5)
            </button>
            <button
              onClick={() => handleQuickLogin('super1', 'password123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-300 border border-yellow-500/20 transition-all"
            >
              ผบก.ทล. (ส่วนกลาง)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
