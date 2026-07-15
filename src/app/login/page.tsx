'use strict';
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const result = await res.json();

      if (res.ok && result.status === 'success') {
        // Redirect to main workspace
        router.push('/');
        router.refresh();
      } else {
        setError(result.message || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง');
      }
    } catch (err: any) {
      setError('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center animated-bg px-4">
      <div className="w-full max-w-md p-8 glass-card">
        {/* Emblem or Logo Placeholder */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-tr from-amber-500 to-yellow-300 rounded-full flex items-center justify-center shadow-lg mb-4 border border-amber-400">
            <i className="fa-solid fa-shield-halved text-slate-900 text-4xl"></i>
          </div>
          <h1 className="text-3xl font-extrabold tracking-wide text-center">
            <span className="gradient-text">HWPD</span> <span className="text-white">NEXT GEN</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1 font-medium tracking-wider">
            HIGHWAY POLICE WORKING & DASHBOARD
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/20 border border-rose-500/50 rounded-lg text-rose-200 text-sm flex items-center gap-3">
            <i className="fa-solid fa-triangle-exclamation text-rose-400 text-base"></i>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">
              ชื่อผู้ใช้งาน (Username)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
                <i className="fa-regular fa-user"></i>
              </span>
              <input
                type="text"
                required
                disabled={loading}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="กรอกชื่อผู้ใช้งาน..."
                className="form-input-premium w-full pl-10 pr-4 py-3 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">
              รหัสผ่าน (Password)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
                <i className="fa-solid fa-key"></i>
              </span>
              <input
                type="password"
                required
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="กรอกรหัสผ่าน..."
                className="form-input-premium w-full pl-10 pr-4 py-3 text-sm"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-premium w-full py-3.5 rounded-lg flex items-center justify-center gap-2 cursor-pointer"
          >
            {loading ? (
              <>
                <i className="fa-solid fa-circle-notch animate-spin text-lg"></i>
                <span>กำลังเข้าสู่ระบบ...</span>
              </>
            ) : (
              <>
                <i className="fa-solid fa-right-to-bracket text-lg"></i>
                <span>เข้าสู่ระบบ</span>
              </>
            )}
          </button>
        </form>

        <div className="mt-8 text-center text-xs text-slate-500 border-t border-slate-800 pt-6">
          ระบบสารสนเทศตำรวจทางหลวง © {new Date().getFullYear()}
        </div>
      </div>
    </main>
  );
}
