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

  changePassword: async (
    username: string,
    oldPassword: string,
    newPassword: string,
    token?: string,
  ): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ username, oldPassword, newPassword }),
      });
      return await res.json();
    } catch (e) {
      if (typeof window !== 'undefined' && (window as any).google?.script?.run) {
        return new Promise((resolve) => {
          (window as any).google.script.run
            .withSuccessHandler(resolve)
            .withFailureHandler((err: any) => resolve({ status: 'error', message: err.message }))
            .changeUserPassword(username, oldPassword, newPassword);
        });
      }
      return { status: 'success', message: 'เปลี่ยนรหัสผ่านสำเร็จ (Demo Mode)' };
    }
  },

  submitReport: async (endpoint: string, formData: any, token?: string, extra?: Record<string, any>) => {
    try {
      const res = await fetch(`${API_BASE_URL}/reports/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-token': token || '',
        },
        body: JSON.stringify({ formData, ...extra }),
      });
      return await res.json();
    } catch (e) {
      return { status: 'success', message: 'บันทึกรายงานสำเร็จ (Demo Mode)' };
    }
  },

  // ---- Dropdown / reference data (with offline demo fallbacks) ----
  getUnitDropdown: async (stationId: string): Promise<string[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/dropdowns/units?station=${encodeURIComponent(stationId)}`);
      const data = await res.json();
      if (Array.isArray(data)) return data;
      if (Array.isArray(data?.units)) return data.units;
      throw new Error('bad shape');
    } catch {
      return ['หน่วยฯดอนจาน', 'หน่วยฯจอมทอง', 'หน่วยฯสามเงา', 'หน่วยฯคลองขลุง'];
    }
  },

  getUserDropdown: async (stationId: string): Promise<string[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/dropdowns/users?station=${encodeURIComponent(stationId)}`);
      const data = await res.json();
      if (Array.isArray(data)) return data;
      if (Array.isArray(data?.users)) return data.users;
      throw new Error('bad shape');
    } catch {
      return ['ด.ต. สมชาย สายตรวจ', 'ส.ต.อ. รักชาติ มั่นคง', 'ร.ต.อ. วีระ ยุติธรรม', 'จ.ส.ต. ประยุทธ อดทน'];
    }
  },

  getChargeDropdown: async (): Promise<string[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/dropdowns/charges`);
      const data = await res.json();
      if (Array.isArray(data)) return data;
      if (Array.isArray(data?.charges)) return data.charges;
      throw new Error('bad shape');
    } catch {
      return [
        'ขับรถเร็วเกินกำหนด',
        'ไม่สวมหมวกนิรภัย',
        'ไม่คาดเข็มขัดนิรภัย',
        'ขับขี่ในขณะเมาสุรา',
        'ไม่มีใบอนุญาตขับขี่',
        'บรรทุกน้ำหนักเกิน',
      ];
    }
  },

  getUserPhoneMapping: async (stationId: string): Promise<Record<string, string>> => {
    try {
      const res = await fetch(`${API_BASE_URL}/dropdowns/user-phones?station=${encodeURIComponent(stationId)}`);
      const data = await res.json();
      if (data && typeof data === 'object') return data;
      throw new Error('bad shape');
    } catch {
      return {};
    }
  },

  // ---- Mission view / history queries ----
  fetchMissions: async (unit: string, start: string, end: string, station: string): Promise<{ status: string; data: any[]; message?: string }> => {
    try {
      const q = new URLSearchParams({ unit, start, end, station }).toString();
      const res = await fetch(`${API_BASE_URL}/missions?${q}`);
      return await res.json();
    } catch {
      return { status: 'success', data: [] };
    }
  },

  getMyPendingItems: async (username: string): Promise<{ status: string; data: any[]; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/my-pending?username=${encodeURIComponent(username)}`);
      return await res.json();
    } catch {
      return { status: 'success', data: [] };
    }
  },

  getDailySummary: async (station: string, start: string, end: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ station, start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/daily-summary?${q}`);
      return await res.json();
    } catch {
      return { status: 'success', data: { v43: 0, service: 0, v42: 0, v20: 0, chargesText: 'ไม่มีข้อมูลข้อหา' } };
    }
  },

  getDivisionSummary: async (station: string, start: string, end: string, token?: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ station, start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/division-summary?${q}`, { headers: { 'x-token': token || '' } });
      return await res.json();
    } catch {
      const div = String(station || '5').charAt(0) || '5';
      const byStation = [1, 2, 3, 4, 5, 6].map((s) => ({
        station: `${div}${s}`, name: `ส.ทล.${s}`,
        arrest: [12, 8, 15, 6, 20, 10][s - 1], royalGuard: [2, 1, 3, 0, 4, 1][s - 1],
        v20: [30, 22, 38, 15, 45, 25][s - 1], service: [55, 40, 62, 30, 70, 48][s - 1], volunteer: [4, 2, 6, 1, 8, 3][s - 1],
        v43: [70, 55, 82, 40, 95, 60][s - 1],
      }));
      const sum = (k: string) => byStation.reduce((a, b: any) => a + b[k], 0);
      return {
        status: 'success',
        data: {
          totals: { arrest: sum('arrest'), v20: sum('v20'), v43: sum('v43'), service: sum('service'), volunteer: sum('volunteer'), royalGuard: sum('royalGuard'), accident: 24, mission: 18 },
          byStation,
          seizedBreakdown: { 'ยาเสพติด': 42, 'อาวุธปืน': 8, 'บุหรี่ไฟฟ้า': 15, 'สินค้าหนีภาษี': 6, 'อื่นๆ': 11 },
          chargeBreakdown: { 'ขับรถเร็วเกินกำหนด': 60, 'ไม่สวมหมวกนิรภัย': 48, 'เมาแล้วขับ': 30, 'ยาเสพติด': 25 },
          accCauseBreakdown: { human: 62, vehicle: 20, road: 12, env: 6 },
          trend: Array.from({ length: 7 }, (_, i) => ({ date: `${i + 1}/7`, arrest: [30, 45, 38, 52, 41, 60, 48][i], service: [40, 55, 48, 62, 51, 70, 58][i] })),
        },
      };
    }
  },

  getStationPending: async (station: string, token?: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/station-pending?station=${encodeURIComponent(station)}`, { headers: { 'x-token': token || '' } });
      return await res.json();
    } catch {
      return {
        status: 'success',
        data: {
          pending: [
            { recordId: 'ARR-260722-1400-101', timestamp: '22/07/2569 14:00', formType: 'รายงานจับกุม (พ.ร.บ.ยาเสพติดฯ)', icon: 'fa-handcuffs', reporter: 'ด.ต. สมชาย สายตรวจ', unit: 'หน่วยฯดอนจาน', details: 'ของกลาง ยาบ้า 200 เม็ด ผู้ต้องหา 1 คน', sheetName: 'tb_Arrests' },
            { recordId: 'ARR-260722-1130-204', timestamp: '22/07/2569 11:30', formType: 'รายงานจับกุม (พ.ร.บ.จราจรทางบก)', icon: 'fa-handcuffs', reporter: 'ส.ต.อ. รักชาติ มั่นคง', unit: 'หน่วยฯจอมทอง', details: 'เมาแล้วขับ วัดปริมาณแอลกอฮอล์ได้ 120 mg%', sheetName: 'tb_Arrests' },
            { recordId: 'OP-260722-0800-051', timestamp: '22/07/2569 08:00', formType: 'ผลการปฏิบัติประจำวัน', icon: 'fa-clipboard-list', reporter: 'ด.ต. สมชาย สายตรวจ', unit: 'หน่วยฯดอนจาน', details: 'ว.43 = 12, บริการ = 5, ว.20 = 3', sheetName: 'tb_DailyResult' },
          ],
          fuel: [
            { recordId: 'FUEL-260722-1000-011', timestamp: '22/07/2569 10:00', plate: 'กท 5101', details: 'ดีเซล 40.5 ลิตร 1,200 บาท', sheetName: 'tb_Fuel' },
          ],
          stats: { pendingCount: 3, fuelCount: 1, approvedToday: 8, v43: 148, v42: 22, v20: 31, arrest: 12, volunteer: 5, royalGuard: 2 },
        },
      };
    }
  },

  approveItem: async (sheetName: string, recordId: string, token?: string): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/records/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-token': token || '' }, body: JSON.stringify({ sheetName, recordId }) });
      return await res.json();
    } catch {
      return { status: 'success', message: 'อนุมัติรายการเรียบร้อย (Demo Mode)' };
    }
  },

  getNationalSummary: async (start: string, end: string, token?: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/national-summary?${q}`, { headers: { 'x-token': token || '' } });
      return await res.json();
    } catch {
      // Offline demo dataset so the charts render.
      const divs = [1, 2, 3, 4, 5, 6, 7, 8].map((d) => ({
        div: String(d), divName: `กก.${d}`,
        arrestsCount: [42, 31, 55, 28, 68, 37, 24, 49][d - 1],
        v20Count: [120, 95, 140, 80, 175, 110, 70, 130][d - 1],
        accCount: [12, 8, 15, 6, 20, 10, 5, 14][d - 1],
        missionCount: [7, 5, 9, 4, 12, 6, 3, 8][d - 1],
      }));
      const totals = divs.reduce((a, d) => ({
        arrestsCount: a.arrestsCount + d.arrestsCount, v20Count: a.v20Count + d.v20Count,
        accCount: a.accCount + d.accCount, missionCount: a.missionCount + d.missionCount, royalCount: a.royalCount,
      }), { arrestsCount: 0, v20Count: 0, accCount: 0, missionCount: 0, royalCount: 9 });
      const trend = Array.from({ length: 7 }, (_, i) => ({
        date: `${i + 1}/7`, arrestsCount: [30, 45, 38, 52, 41, 60, 48][i], accCount: [8, 12, 9, 15, 10, 18, 11][i],
      }));
      return {
        status: 'success',
        data: {
          totals,
          byDivision: divs,
          trend,
          arrestTypeBreakdown: { 'จับกุมซึ่งหน้า': 210, 'จับตามหมาย': 95, 'จับหมาย Bigdata': 48, 'จับหมาย Bodyworn': 30 },
          chargeBreakdown: { 'ขับรถเร็วเกินกำหนด': 180, 'ไม่สวมหมวกนิรภัย': 150, 'เมาแล้วขับ': 90, 'ยาเสพติด': 75, 'ไม่มีใบขับขี่': 60 },
          accCauseBreakdown: { human: 62, vehicle: 20, road: 12, env: 6 },
        },
      };
    }
  },

  cancelRecord: async (sheetName: string, recordId: string, username: string, token?: string): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/records/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ sheetName, recordId, username }),
      });
      return await res.json();
    } catch {
      return { status: 'success', message: 'ยกเลิกรายการเรียบร้อย (Demo Mode)' };
    }
  },
};
