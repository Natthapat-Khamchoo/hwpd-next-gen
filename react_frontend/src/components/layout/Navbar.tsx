import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Shield, LogOut, User as UserIcon, Building2 } from 'lucide-react';

interface NavbarProps {
  onGoHome: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onGoHome }) => {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 px-4 py-3 border-b border-white/10 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo & Name */}
        <div 
          onClick={onGoHome}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-yellow-300 p-0.5 shadow-lg shadow-yellow-500/20 group-hover:scale-105 transition-transform">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Shield className="w-5 h-5 text-yellow-400" />
            </div>
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight bg-gradient-to-r from-yellow-300 via-amber-200 to-white bg-clip-text text-transparent">
              HWPD Next Gen
            </h1>
            <p className="text-[10px] text-slate-400 tracking-wider font-semibold uppercase">
              กองบังคับการตำรวจทางหลวง (บก.ทล.)
            </p>
          </div>
        </div>

        {/* User Info & Actions */}
        {user ? (
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3 bg-white/5 px-3 py-1.5 rounded-xl border border-white/10">
              <div className="text-right">
                <div className="text-xs font-semibold text-white flex items-center justify-end gap-1.5">
                  <UserIcon className="w-3.5 h-3.5 text-cyan-400" />
                  {user.fullName}
                </div>
                <div className="text-[11px] text-slate-400 flex items-center justify-end gap-1">
                  <Building2 className="w-3 h-3 text-amber-400" />
                  {user.unit} (กก.{user.station ? user.station[0] : '5'})
                </div>
              </div>
            </div>

            <button
              onClick={logout}
              className="p-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:border-red-500/40 transition-all text-xs font-medium flex items-center gap-1.5"
              title="ออกจากระบบ"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden md:inline">ออกจากระบบ</span>
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
};
