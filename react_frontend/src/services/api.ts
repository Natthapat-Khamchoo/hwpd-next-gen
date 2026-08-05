import type { MapPointsData, RecordDetail, User } from '../types';

// Set VITE_API_BASE_URL on the host (e.g. Vercel) to point at a deployed backend.
// Falls back to localhost for dev; if unreachable, api.* methods use offline demo data.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000/api';

// Local user directory — mirrors the tb_Users Google Sheet exactly (password: 1234).
// Used as the offline fallback when the backend is unreachable (e.g. the Vercel site).
// The backend now rejects writes without a valid session token. AuthContext
// registers a handler here so a 401 sends the officer back to the login screen
// instead of leaving them staring at a generic "บันทึกไม่สำเร็จ".
let onSessionExpired: () => void = () => {};
export const setSessionExpiredHandler = (handler: () => void) => {
  onSessionExpired = handler;
};

export const SESSION_EXPIRED_MESSAGE = 'Session หมดอายุ กรุณาเข้าสู่ระบบใหม่';

/** Pull a human-readable reason out of a FastAPI error body. */
const errorMessage = (body: any, fallback: string): string => {
  const detail = body?.detail ?? body?.message;
  if (typeof detail === 'string' && detail.trim()) return detail;
  // 422 from Pydantic arrives as a list of {loc, msg, type}.
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: any) => `${(d?.loc || []).slice(1).join('.')}: ${d?.msg}`).join(', ');
  }
  return fallback;
};

// โหมดสาธิตต้องเปิดด้วย VITE_DEMO_MODE=true ตอน build เท่านั้น ไม่ใช่เปิดเองเมื่อ
// ต่อ backend ไม่ได้ ไม่งั้นเจ้าหน้าที่จะเห็นข้อความว่าบันทึกสำเร็จทั้งที่ข้อมูลหาย
// และตัวเว็บที่ deploy จริงจะกลายเป็นระบบที่ใครก็เข้าได้
export const DEMO_MODE = String(import.meta.env.VITE_DEMO_MODE ?? '').toLowerCase() === 'true';

const OFFLINE_MESSAGE = 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองใหม่';

/**
 * ดึงข้อมูลอ้างอิงที่ต้องมี session (dropdown ทุกตัว) คืน null เมื่อเรียกไม่สำเร็จ
 * ให้ผู้เรียกตัดสินใจเองว่าจะใช้ค่าสำรองหรือรายการว่าง
 *
 * 401 หมายถึง session หมดอายุ ต้องพากลับไปหน้าล็อกอิน ไม่ใช่ปล่อยให้เจ้าหน้าที่
 * เห็น dropdown ว่างแล้วเดาเองว่าระบบพัง
 */
const fetchReference = async (path: string, token?: string): Promise<unknown | null> => {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { headers: { 'x-token': token || '' } });
    if (res.status === 401) {
      onSessionExpired();
      return null;
    }
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
};

/** ตัวช่วยสำหรับ dropdown ที่คืนเป็นรายการ รองรับทั้ง [...] และ {key: [...]} */
const fetchList = async (
  path: string,
  key: string,
  token: string | undefined,
  demoFallback: string[],
): Promise<string[]> => {
  const data = await fetchReference(path, token);
  if (Array.isArray(data)) return data;
  if (Array.isArray((data as any)?.[key])) return (data as any)[key];
  return DEMO_MODE ? demoFallback : [];
};

/**
 * ตัวช่วยของ endpoint ชุด ฝอ.กก./ผู้กำกับการ
 *
 * ทุกตัวคืนรูปเดียวกัน { status, data?, message? } และแปลง error ของ FastAPI เป็น
 * ข้อความไทยให้แล้ว หน้าเรียกจึงเช็ค status ที่เดียวพอ ไม่ต้อง try/catch เอง
 *
 * ไม่มีข้อมูลสำรองในโหมดสาธิตเหมือน getDivisionSummary เพราะหน้าพวกนี้เป็นงานธุรการ
 * ที่ต้องอ่านของจริง ตัวเลขปลอมบนหน้าโควตาน้ำมันหรือกำลังพลอันตรายกว่าการขึ้นว่า
 * ต่อเซิร์ฟเวอร์ไม่ได้
 */
/**
 * `contacts` ใช้เฉพาะ `/commander/order` ที่คืนเบอร์หัวหน้าหน่วยปลายทางมาด้วย
 * (requirement ข้อ 2) endpoint อื่นไม่ส่งฟิลด์นี้
 */
export interface OrderContact {
  station: string;
  stationName: string;
  heads: { name: string; role: string; phone: string; station: string }[];
}

type HqResult<T = any> = { status: string; data?: T; message?: string; contacts?: OrderContact[] };

const hqRequest = async (path: string, init: RequestInit, token?: string): Promise<HqResult> => {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { ...(init.headers || {}), 'x-token': token || '' },
    });
    const body = await res.json().catch(() => ({}));
    if (res.status === 401) {
      onSessionExpired();
      return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
    }
    if (!res.ok) return { status: 'error', message: errorMessage(body, 'เรียกข้อมูลไม่สำเร็จ') };
    return body;
  } catch {
    return { status: 'error', message: OFFLINE_MESSAGE };
  }
};

const hqGet = (path: string, params: Record<string, string>, token?: string): Promise<HqResult> => {
  // ตัดค่าว่างทิ้งก่อน ไม่งั้น start= จะไปทับค่า default ฝั่ง server ด้วยสตริงว่าง
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value),
  ).toString();
  return hqRequest(`${path}${query ? `?${query}` : ''}`, { method: 'GET' }, token);
};

const hqPost = (path: string, body: Record<string, unknown>, token?: string): Promise<HqResult> =>
  hqRequest(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, token);

export const api = {
  login: async (username: string, password: string): Promise<{ status: string; user?: User; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok) return body;
      return { status: 'error', message: errorMessage(body, `เข้าสู่ระบบไม่สำเร็จ (HTTP ${res.status})`) };
    } catch (error) {
      if (typeof window !== 'undefined' && (window as any).google?.script?.run) {
        return new Promise((resolve) => {
          (window as any).google.script.run
            .withSuccessHandler(resolve)
            .withFailureHandler((err: any) => resolve({ status: 'error', message: err.message }))
            .checkLogin(username, password);
        });
      }
      return { status: 'error', message: OFFLINE_MESSAGE };
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
      if (DEMO_MODE) return { status: 'success', message: 'เปลี่ยนรหัสผ่านสำเร็จ (โหมดสาธิต)' };
      return { status: 'error', message: OFFLINE_MESSAGE };
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
      const body = await res.json().catch(() => ({}));

      if (res.ok) return body;

      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
      }
      if (res.status === 404) {
        return {
          status: 'error',
          message: `ระบบยังไม่รองรับการบันทึกรายงานประเภทนี้ (${endpoint}) กรุณาแจ้งผู้ดูแลระบบ`,
        };
      }
      return { status: 'error', message: errorMessage(body, `บันทึกไม่สำเร็จ (HTTP ${res.status})`) };
    } catch (e) {
      if (DEMO_MODE) return { status: 'success', message: 'บันทึกรายงานสำเร็จ (โหมดสาธิต ข้อมูลไม่ถูกบันทึกจริง)' };
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  // ---- Dropdown / reference data (demo fallbacks only when VITE_DEMO_MODE=true) ----
  getUnitDropdown: async (stationId: string, token?: string): Promise<string[]> =>
    fetchList(`/dropdowns/units?station=${encodeURIComponent(stationId)}`, 'units', token, [
      'คลองขลุง',
      'นครชุม',
      'สามเงา',
      'แม่สอด',
    ]),

  getUserDropdown: async (stationId: string, token?: string): Promise<string[]> =>
    fetchList(`/dropdowns/users?station=${encodeURIComponent(stationId)}`, 'users', token, [
      'ด.ต. สมชาย สายตรวจ',
      'ส.ต.อ. รักชาติ มั่นคง',
      'ร.ต.อ. วีระ ยุติธรรม',
      'จ.ส.ต. ประยุทธ อดทน',
    ]),

  getChargeDropdown: async (token?: string): Promise<string[]> =>
    fetchList('/dropdowns/charges', 'charges', token, [
      'ขับรถเร็วเกินกำหนด',
      'ไม่สวมหมวกนิรภัย',
      'ไม่คาดเข็มขัดนิรภัย',
      'ขับขี่ในขณะเมาสุรา',
      'ไม่มีใบอนุญาตขับขี่',
      'บรรทุกน้ำหนักเกิน',
    ]),

  getUserPhoneMapping: async (stationId: string, token?: string): Promise<Record<string, string>> => {
    const data = await fetchReference(
      `/dropdowns/user-phones?station=${encodeURIComponent(stationId)}`,
      token,
    );
    return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, string>) : {};
  },

  // ---- Mission view / history queries ----
  fetchMissions: async (unit: string, start: string, end: string, station: string, token?: string): Promise<{ status: string; data: any[]; message?: string }> => {
    try {
      const q = new URLSearchParams({ unit, start, end, station }).toString();
      const res = await fetch(`${API_BASE_URL}/missions?${q}`, { headers: { 'x-token': token || '' } });
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', data: [], message: SESSION_EXPIRED_MESSAGE };
      }
      return await res.json();
    } catch {
      return { status: 'error', data: [], message: OFFLINE_MESSAGE };
    }
  },

  getMyPendingItems: async (username: string, token?: string): Promise<{ status: string; data: any[]; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/my-pending?username=${encodeURIComponent(username)}`, {
        headers: { 'x-token': token || '' },
      });
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', data: [], message: SESSION_EXPIRED_MESSAGE };
      }
      return await res.json();
    } catch {
      return { status: 'error', data: [], message: OFFLINE_MESSAGE };
    }
  },

  getDailySummary: async (station: string, start: string, end: string, token?: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ station, start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/daily-summary?${q}`, { headers: { 'x-token': token || '' } });
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
      }
      return await res.json();
    } catch {
      if (DEMO_MODE) return { status: 'success', data: { v43: 0, service: 0, v42: 0, v20: 0, chargesText: 'ไม่มีข้อมูลข้อหา' } };
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /** ตารางอ้างอิงที่ บก. แก้ได้ — kind: charges | seized-items | report-catalog */
  getReferenceTable: async (kind: string, token?: string): Promise<{
    status: string; data?: any[]; keyColumn?: string; activeColumn?: string | null; label?: string; message?: string;
  }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/reference/${kind}`, { headers: { 'x-token': token || '' } });
      if (res.status === 403) return { status: 'error', message: 'ไม่มีสิทธิ์แก้ข้อมูลอ้างอิงของระบบ' };
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  saveReferenceRow: async (
    kind: string,
    values: Record<string, string>,
    originalKey: string | null,
    token?: string,
  ): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/reference/${kind}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ values, originalKey }),
      });
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  setReferenceRowActive: async (
    kind: string, key: string, active: boolean, token?: string,
  ): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/reference/${kind}/active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ key, active }),
      });
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /**
   * ค้นหาเชิงลึก — scope 'division' คือในกองตัวเอง 'national' คือทุก กก.
   *
   * ยิงเฉพาะตอนกดค้นหา ระดับประเทศต้องเปิด 8 สเปรดชีต x 7 ตาราง จึงไม่ควรโหลดเอง
   */
  deepSearch: async (
    scope: 'division' | 'national',
    params: { keyword: string; start: string; end: string; station?: string },
    token?: string,
  ): Promise<{ status: string; data?: any[]; message?: string }> => {
    try {
      const q = new URLSearchParams({
        keyword: params.keyword,
        start: params.start,
        end: params.end,
        ...(scope === 'division' && params.station ? { station: params.station } : {}),
      }).toString();
      const res = await fetch(`${API_BASE_URL}/search/${scope}?${q}`, { headers: { 'x-token': token || '' } });
      if (res.status === 403) return { status: 'error', message: 'ไม่มีสิทธิ์ค้นหาข้อมูลระดับนี้' };
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /**
   * พิกัดสำหรับหน้าแผนที่ (requirement ข้อ 4)
   *
   * ส่งเฉพาะชั้นที่เปิดอยู่ ชั้นที่ผู้ใช้ปิดไว้จะไม่ถูกอ่านจากชีตเลย ซึ่งสำคัญกับระบบนี้
   * เพราะโควตาการอ่านของ Google คิดเป็นจำนวนคำขอ ไม่ใช่ปริมาณข้อมูล
   */
  getMapPoints: async (
    params: {
      station?: string;
      start?: string;
      end?: string;
      layers: string[];
      charge?: string;
      unit?: string;
      stationFilter?: string;
    },
    token?: string,
  ): Promise<{ status: string; data?: MapPointsData; message?: string }> => {
    try {
      const q = new URLSearchParams({ layers: params.layers.join(',') });
      (['station', 'start', 'end', 'charge', 'unit', 'stationFilter'] as const).forEach((key) => {
        const value = params[key];
        if (value) q.set(key, value);
      });
      const res = await fetch(`${API_BASE_URL}/map/points?${q.toString()}`, {
        headers: { 'x-token': token || '' },
      });
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
      }
      if (res.status === 403) return { status: 'error', message: 'ไม่มีสิทธิ์ดูข้อมูลของสถานีนี้' };
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /** แบบฟอร์มที่ออกเป็น Excel ได้ตอนนี้ — รายการมาจากฝั่ง API ไม่ฮาร์ดโค้ดสองที่ */
  getExportableReports: async (token?: string): Promise<{ reportKey: string; title: string; cadence: string }[]> => {
    const res = await fetchReference('/reports/catalog/exportable', token);
    const data = (res as { data?: unknown })?.data;
    return Array.isArray(data) ? (data as { reportKey: string; title: string; cadence: string }[]) : [];
  },

  /** ทำเนียบผู้ใช้ทั้งหมด สำหรับหน้าจัดการผู้ใช้งานของ บก. (ไม่มีคอลัมน์รหัสผ่าน) */
  getAllUsers: async (token?: string): Promise<any[]> => {
    const res = await fetchReference('/admin/users', token);
    const data = (res as { data?: unknown })?.data;
    return Array.isArray(data) ? data : [];
  },

  /** แก้ชื่อจริง/เบอร์โทร — ส่งเฉพาะช่องที่แก้ ช่องที่ไม่ส่งจะไม่ถูกแตะ */
  updateUserProfile: async (
    username: string,
    patch: { fullName?: string; phone?: string },
    token?: string,
  ): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ username, ...patch }),
      });
      return await res.json();
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /**
   * สถานะฐานข้อมูลราย กก. ใช้ทำเมนู "เจาะลึกรายกองกำกับ"
   *
   * ของเดิมเรียก getNationalDivisionOptions() เพื่อรู้ว่า กก. ไหนตั้งค่าฐานข้อมูลแล้ว
   * จะได้ทำตัวที่ยังไม่พร้อมให้จางและกดไม่ได้ ฝั่ง Python ไม่มี endpoint ชื่อนั้น แต่
   * /health/database คืนข้อมูลชุดเดียวกันอยู่แล้ว (division + status ครบทั้ง 8)
   */
  getDatabaseHealth: async (token?: string): Promise<{ division: string; status: string; title?: string }[]> => {
    const res = await fetchReference('/health/database', token);
    const divisions = (res as { divisions?: unknown })?.divisions;
    return Array.isArray(divisions) ? (divisions as { division: string; status: string; title?: string }[]) : [];
  },

  getDivisionSummary: async (station: string, start: string, end: string, token?: string): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ station, start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/division-summary?${q}`, { headers: { 'x-token': token || '' } });
      return await res.json();
    } catch {
      if (!DEMO_MODE) return { status: 'error', message: OFFLINE_MESSAGE };
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
      if (!DEMO_MODE) return { status: 'error', message: OFFLINE_MESSAGE };
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

  /**
   * ข้อหาที่จัดกลุ่มตาม พ.ร.บ. แล้ว (requirement ข้อ 14)
   * คืนทั้งแบบกลุ่มและแบบรายชื่อล้วนในคำขอเดียว หน้าเว็บจึงสลับได้โดยไม่ยิงซ้ำ
   */
  getChargeGroups: async (
    token?: string,
  ): Promise<{ groups: { group: string; charges: string[] }[]; flat: string[] }> => {
    const res = await fetchReference('/dropdowns/charges-grouped', token);
    const data = (res as { data?: { groups?: unknown; flat?: unknown } })?.data;
    return {
      groups: Array.isArray(data?.groups) ? (data.groups as { group: string; charges: string[] }[]) : [],
      flat: Array.isArray(data?.flat) ? (data.flat as string[]) : [],
    };
  },

  // ------------------------------------------- โมดูลประชาสัมพันธ์ (requirement ข้อ 13)

  /** ส่งข่าวเข้าคิวตรวจ (FR-01) — `mediaMeta` คือค่าที่วัดจากเบราว์เซอร์ */
  submitPrNews: async (
    formData: Record<string, unknown>,
    token?: string,
    files?: { name: string; type: string; data: string }[],
  ): Promise<{ status: string; message?: string; needsMediaReview?: boolean; matchedKeywords?: string[] }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/pr/news`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ formData, files: files || [] }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
      }
      if (!res.ok) return { status: 'error', message: errorMessage(body, 'ส่งข่าวไม่สำเร็จ') };
      return body;
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /** ตารางรวมข่าวพร้อมตัวกรองและยอดสรุป (FR-04) */
  listPrNews: (params: Record<string, string>, token?: string) =>
    hqGet('/pr/news', params, token),

  /** ไฟล์สื่อของข่าวหนึ่งใบ ใช้ตอนแอดมินตรวจ */
  prNewsMedia: (recordId: string, station: string, token?: string) =>
    hqGet('/pr/news/media', { recordId, station }, token),

  /** อนุมัติหรือปฏิเสธข่าว (FR-09) */
  decidePrNews: (body: Record<string, unknown>, token?: string) =>
    hqPost('/pr/news/decide', body, token),

  /** คำค้นที่แอดมินตั้งไว้ (FR-02) */
  getPrKeywords: async (
    token?: string,
  ): Promise<{ keyword: string; category: string; note: string; isActive: boolean }[]> => {
    const res = await fetchReference('/pr/keywords', token);
    const data = (res as { data?: unknown })?.data;
    return Array.isArray(data)
      ? (data as { keyword: string; category: string; note: string; isActive: boolean }[])
      : [];
  },

  /** เพิ่มคำค้น (FR-09) — แอดมินเท่านั้น */
  savePrKeyword: (body: Record<string, unknown>, token?: string) =>
    hqPost('/pr/keywords', body, token),

  /** เทมเพลตชิ้นงาน PR ที่มีให้เลือก (FR-07) */
  getPrTemplates: async (token?: string): Promise<{ key: string; label: string }[]> => {
    const res = await fetchReference('/pr/templates', token);
    const data = (res as { data?: unknown })?.data;
    return Array.isArray(data) ? (data as { key: string; label: string }[]) : [];
  },

  /** ประกอบชิ้นงาน PR ตามเทมเพลตเพื่อดูก่อน ยังไม่แชร์ (FR-07) */
  composePrNews: (body: Record<string, unknown>, token?: string) =>
    hqPost('/pr/news/compose', body, token),

  /** อัปชิ้นงานขึ้น Drive แล้วคืนลิงก์สาธารณะแบบอ่านอย่างเดียว (FR-08) */
  sharePrNews: (body: Record<string, unknown>, token?: string) =>
    hqPost('/pr/news/share', body, token),

  /** ถอนลิงก์สาธารณะที่เคยสร้างไว้ (FR-08) */
  revokePrShare: (body: Record<string, unknown>, token?: string) =>
    hqPost('/pr/news/share/revoke', body, token),

  /** รายงานข่าวค้างอนุมัติแยกตามสังกัด (FR-10) */
  prPendingReport: (params: Record<string, string>, token?: string) =>
    hqGet('/pr/report/pending', params, token),

  /** รายละเอียดเต็มของรายการ พร้อมไฟล์แนบ (requirement ข้อ 9) */
  getRecordDetail: async (
    sheetName: string,
    recordId: string,
    token?: string,
  ): Promise<{ status: string; data?: RecordDetail; message?: string }> => {
    const q = new URLSearchParams({ sheetName, recordId }).toString();
    try {
      const res = await fetch(`${API_BASE_URL}/records/detail?${q}`, { headers: { 'x-token': token || '' } });
      if (res.status === 401) {
        onSessionExpired();
        return { status: 'error', message: SESSION_EXPIRED_MESSAGE };
      }
      const body = await res.json().catch(() => ({}));
      if (!res.ok) return { status: 'error', message: errorMessage(body, 'ดึงรายละเอียดไม่สำเร็จ') };
      return body;
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /** แก้ไขรายการของตัวเองที่ยังรออนุมัติ (requirement ข้อ 10) */
  updateRecord: async (
    sheetName: string,
    recordId: string,
    updates: Record<string, string>,
    token?: string,
  ): Promise<{ status: string; message?: string; changed?: number }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/records/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-token': token || '' },
        body: JSON.stringify({ sheetName, recordId, updates }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) return { status: 'error', message: errorMessage(body, 'แก้ไขไม่สำเร็จ') };
      return body;
    } catch {
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  approveItem: async (sheetName: string, recordId: string, token?: string): Promise<{ status: string; message?: string }> => {
    try {
      const res = await fetch(`${API_BASE_URL}/records/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-token': token || '' }, body: JSON.stringify({ sheetName, recordId }) });
      return await res.json();
    } catch {
      if (DEMO_MODE) return { status: 'success', message: 'อนุมัติรายการเรียบร้อย (โหมดสาธิต)' };
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  /**
   * ภาพรวมของ บก.ทล. — ค่าเริ่มต้นนับเฉพาะ กก.8 ตาม requirement ข้อ 3
   * ส่ง `includeArchived` เพื่อดูข้อมูลสำรองของ กก.1-7 ที่ยังเก็บไว้ครบ
   */
  getNationalSummary: async (
    start: string,
    end: string,
    token?: string,
    includeArchived = false,
  ): Promise<{ status: string; data?: any; message?: string }> => {
    try {
      const q = new URLSearchParams({ start, end }).toString()
        + (includeArchived ? '&includeArchived=true' : '');
      const res = await fetch(`${API_BASE_URL}/national-summary?${q}`, { headers: { 'x-token': token || '' } });
      return await res.json();
    } catch {
      if (!DEMO_MODE) return { status: 'error', message: OFFLINE_MESSAGE };
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
      if (DEMO_MODE) return { status: 'success', message: 'ยกเลิกรายการเรียบร้อย (โหมดสาธิต)' };
      return { status: 'error', message: OFFLINE_MESSAGE };
    }
  },

  // ------------------- หน้า ฝอ.กก. และหน้าผู้กำกับการ -------------------

  hqFuel: (station: string, month: string, token?: string) =>
    hqGet('/hq/fuel', { station, month }, token),

  hqSaveFuelQuota: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/fuel/quota', body, token),

  hqManpower: (station: string, token?: string) =>
    hqGet('/hq/manpower', { station }, token),

  hqSaveManpowerStatus: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/manpower/status', body, token),

  hqEvidence: (station: string, start: string, end: string, token?: string) =>
    hqGet('/hq/evidence', { station, start, end }, token),

  hqSaveEvidence: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/evidence', body, token),

  hqEscort: (station: string, start: string, end: string, token?: string) =>
    hqGet('/hq/escort', { station, start, end }, token),

  hqSaveEscort: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/escort', body, token),

  hqDailyDetail: (station: string, start: string, end: string, token?: string) =>
    hqGet('/hq/daily-detail', { station, start, end }, token),

  commanderOverview: (station: string, start: string, end: string, token?: string) =>
    hqGet('/commander/overview', { station, start, end }, token),

  commanderCalendar: (station: string, month: string, token?: string) =>
    hqGet('/commander/calendar', { station, month }, token),

  commanderOrder: (body: Record<string, unknown>, token?: string) =>
    hqPost('/commander/order', body, token),

  /** กก. ที่บัญชีนี้เปิดดูสถิติได้ (requirement ข้อ 1) — ระดับผู้กำกับการขึ้นไปเท่านั้น */
  commanderDivisions: (token?: string) =>
    hqGet('/commander/divisions', {}, token),

  hqAnalysisCategories: (token?: string) =>
    hqGet('/hq/analysis/categories', {}, token),

  hqAnalysis: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/analysis', body, token),

  hqRecords: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/records', body, token),

  hqComparison: (body: Record<string, unknown>, token?: string) =>
    hqPost('/hq/comparison', body, token),

  commanderSummary: (station: string, start: string, end: string, token?: string) =>
    hqGet('/commander/summary', { station, start, end }, token),

};
