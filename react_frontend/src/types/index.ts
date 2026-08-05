export type UserRole =
  | 'Unit_Staff'
  | 'Station_Admin'
  | 'สิบเวร'
  | 'Division_Admin'
  | 'Division_Commander'
  | 'HQ_Admin'
  | 'Super_Commander'
  /** ฝ่ายประชาสัมพันธ์ ระดับ บก. ทำได้เฉพาะงาน PR (ดู PR_ONLY_ROLES ฝั่ง backend) */
  | 'PR_Officer';

export interface User {
  username: string;
  fullName: string;
  station: string;
  unit: string;
  role: UserRole;
  phone?: string;
  code?: string;
  token?: string;
}

export interface StationInfo {
  id: string;
  province: string;
  fullName: string;
  units: string[];
}

export interface ReportItem {
  recordId: string;
  type: string;
  createdAt: string;
  actionBy: string;
  status: 'Pending' | 'Approved' | 'Void' | 'Active';
  stationId: string;
  unitId: string;
  details: string;
}

/** รายละเอียดเต็มของรายงานหนึ่งใบ ใช้ในหน้าตรวจก่อนอนุมัติและหน้าแก้ไขของเจ้าของ */
export interface RecordDetail {
  recordId: string;
  table: string;
  status: string;
  actionBy: string;
  station: string;
  unit: string;
  date: string;
  timestamp: string;
  fields: { label: string; value: string }[];
  attachments: string[];
  /** เจ้าของรายการที่ยังรออนุมัติเท่านั้นที่แก้ได้ (requirement ข้อ 10) */
  canEdit: boolean;
  /** คอลัมน์ที่เปิดให้แก้ ไม่รวมคอลัมน์ระบบและช่องไฟล์แนบ */
  editableFields: string[];
}

/** ชั้นของหน้าแผนที่ ต้องตรงกับคีย์ใน `map_service.LAYERS` ฝั่ง backend */
export type MapLayer = 'crime' | 'checkpoint' | 'accident';

export interface MapPoint {
  layer: MapLayer;
  recordId: string;
  lat: number;
  lng: number;
  date: string;
  station: string;
  unit: string;
  title: string;
  detail: string;
}

export interface MapPointsData {
  points: MapPoint[];
  counts: Record<MapLayer, number>;
  /** จำนวนรายการที่กรอกพิกัดไว้แต่ใช้ไม่ได้ (พิมพ์ผิด/นอกกรอบประเทศไทย) */
  skippedInvalidCoordinates: number;
}

export interface NationalAnalytics {
  totals: {
    arrestsCount: number;
    v20Count: number;
    v43Count: number;
    v42Count: number;
    serviceCount: number;
    accCount: number;
    deadCount: number;
    injuredCount: number;
    volCount: number;
    royalCount: number;
    missionCount: number;
  };
  byDivision: Array<{
    div: string;
    divName: string;
    arrestsCount: number;
    v20Count: number;
    accCount: number;
    missionCount: number;
  }>;
}
