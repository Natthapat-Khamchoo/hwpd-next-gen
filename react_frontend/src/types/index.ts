export type UserRole =
  | 'Unit_Staff'
  | 'Station_Admin'
  | 'สิบเวร'
  | 'Division_Admin'
  | 'Division_Commander'
  | 'HQ_Admin'
  | 'Super_Commander';

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
