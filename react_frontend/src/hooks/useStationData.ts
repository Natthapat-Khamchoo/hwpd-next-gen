import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export interface ChargeGroup {
  group: string;
  charges: string[];
}

export interface StationData {
  units: string[];
  users: string[];
  charges: string[];
  /** ข้อหาที่จัดกลุ่มตาม พ.ร.บ. แล้ว (requirement ข้อ 14) ว่างได้ถ้าโหลดไม่สำเร็จ */
  chargeGroups: ChargeGroup[];
  phoneMap: Record<string, string>;
  loading: boolean;
}

/** Loads unit / user / charge dropdowns + phone mapping for the logged-in user's station. */
export const useStationData = (opts: { charges?: boolean } = {}): StationData => {
  const { user } = useAuth();
  const station = user?.station || '51';
  const token = user?.token;
  const [units, setUnits] = useState<string[]>([]);
  const [users, setUsers] = useState<string[]>([]);
  const [charges, setCharges] = useState<string[]>([]);
  const [chargeGroups, setChargeGroups] = useState<ChargeGroup[]>([]);
  const [phoneMap, setPhoneMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const jobs: Promise<void>[] = [
      api.getUnitDropdown(station, token).then((u) => { if (alive) setUnits(u); }),
      api.getUserDropdown(station, token).then((u) => { if (alive) setUsers(u); }),
      api.getUserPhoneMapping(station, token).then((m) => { if (alive) setPhoneMap(m); }),
    ];
    if (opts.charges) {
      // ยิงตัวเดียวได้ทั้งรายชื่อล้วนและแบบจัดกลุ่ม ไม่ต้องเรียก getChargeDropdown ซ้ำ
      jobs.push(
        api.getChargeGroups(token).then((res) => {
          if (!alive) return;
          setChargeGroups(res.groups);
          setCharges(res.flat);
        }),
      );
    }
    Promise.all(jobs).finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [station, token]);

  return { units, users, charges, chargeGroups, phoneMap, loading };
};
