import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export interface StationData {
  units: string[];
  users: string[];
  charges: string[];
  phoneMap: Record<string, string>;
  loading: boolean;
}

/** Loads unit / user / charge dropdowns + phone mapping for the logged-in user's station. */
export const useStationData = (opts: { charges?: boolean } = {}): StationData => {
  const { user } = useAuth();
  const station = user?.station || '51';
  const [units, setUnits] = useState<string[]>([]);
  const [users, setUsers] = useState<string[]>([]);
  const [charges, setCharges] = useState<string[]>([]);
  const [phoneMap, setPhoneMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const jobs: Promise<void>[] = [
      api.getUnitDropdown(station).then((u) => { if (alive) setUnits(u); }),
      api.getUserDropdown(station).then((u) => { if (alive) setUsers(u); }),
      api.getUserPhoneMapping(station).then((m) => { if (alive) setPhoneMap(m); }),
    ];
    if (opts.charges) jobs.push(api.getChargeDropdown().then((c) => { if (alive) setCharges(c); }));
    Promise.all(jobs).finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [station]);

  return { units, users, charges, phoneMap, loading };
};
