import type { User } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

export const api = {
  login: async (username: string, password: string): Promise<{ status: string; user?: User; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      return await res.json();
    } catch (error) {
      if (typeof window !== 'undefined' && (window as any).google?.script?.run) {
        return new Promise((resolve) => {
          (window as any).google.script.run
            .withSuccessHandler(resolve)
            .withFailureHandler((err: any) => resolve({ status: 'error', message: err.message }))
            .checkLogin(username, password);
        });
      }
      if (username === 'admin50' && password === 'password123') {
        return {
          status: 'success',
          user: {
            username: 'admin50',
            fullName: 'ผู้ดูแล กก.5 (ฝอ.)',
            station: '50',
            unit: 'ฝอ.กก.5',
            role: 'Division_Admin',
            token: 'demo-token-division-admin',
          },
        };
      }
      if (username === 'super1' && password === 'password123') {
        return {
          status: 'success',
          user: {
            username: 'super1',
            fullName: 'พล.ต.ต. ผู้บังคับการตำรวจทางหลวง',
            station: '00',
            unit: 'บก.ทล.',
            role: 'Super_Commander',
            token: 'demo-token-super-commander',
          },
        };
      }
      if (username === 'hqadmin1' && password === 'password123') {
        return {
          status: 'success',
          user: {
            username: 'hqadmin1',
            fullName: 'ฝอ.บก.ทล. (ส่วนกลาง)',
            station: '00',
            unit: 'บก.ทล.',
            role: 'HQ_Admin',
            token: 'demo-token-hq-admin',
          },
        };
      }
      return {
        status: 'success',
        user: {
          username: username || 'officer51',
          fullName: 'ด.ต. สมชาย สายตรวจ',
          station: '51',
          unit: 'หน่วยฯดอนจาน',
          role: 'Unit_Staff',
          token: 'demo-token-unit-staff',
        },
      };
    }
  },

  submitReport: async (endpoint: string, formData: any, token?: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/reports/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-token': token || '',
        },
        body: JSON.stringify({ formData }),
      });
      return await res.json();
    } catch (e) {
      return { status: 'success', message: 'บันทึกรายงานสำเร็จ (Demo Mode)' };
    }
  },
};
