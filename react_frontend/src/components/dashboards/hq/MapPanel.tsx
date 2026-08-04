import React, { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { useAuth } from '../../../context/AuthContext';
import { useStationData } from '../../../hooks/useStationData';
import { api } from '../../../services/api';
import type { MapLayer, MapPoint, MapPointsData } from '../../../types';

/**
 * แผนที่รวมพิกัดการปฏิบัติ (requirement ข้อ 4)
 *
 * อยู่ในแผงควบคุมของ ฝอ.กก. และผู้กำกับการ ไม่ใช่ในเมนูผู้ปฏิบัติ เพราะเป็นเครื่องมือ
 * วิเคราะห์ภาพรวมของหน่วย ไม่ใช่ฟอร์มบันทึกข้อมูล และเมนูผู้ปฏิบัติของต้นฉบับ
 * Apps Script มี 12 ปุ่มพอดีสามแถว การเพิ่มปุ่มที่ 13 ทำให้แถวสุดท้ายเหลือค้าง
 *
 * สามชั้นเปิด/ปิดแยกกันได้ ชั้นที่ปิดไว้จะไม่ถูกขอจาก backend ในรอบถัดไป ไม่ใช่ขอมา
 * แล้วซ่อน เพราะการอ่านแต่ละตารางกินโควตาของ Google และระบบนี้ใช้บัญชีเดียวทั้งระบบ
 *
 * ใช้ `CircleMarker` แทนหมุดรูปภาพ เพราะหน้านี้วาดได้ถึงหลักพันจุด หมุดที่เป็นภาพ
 * จะสร้าง DOM element ต่อจุด ส่วน CircleMarker วาดลง canvas layer เดียว
 */

const LAYER_META: Record<MapLayer, { label: string; color: string; icon: string }> = {
  crime: { label: 'จุดจับกุม', color: '#dc3545', icon: 'fa-handcuffs' },
  checkpoint: { label: 'จุดตั้งด่าน', color: '#00f2ff', icon: 'fa-road-barrier' },
  accident: { label: 'จุดเกิดอุบัติเหตุ', color: '#ffc107', icon: 'fa-car-burst' },
};

const ALL_LAYERS = Object.keys(LAYER_META) as MapLayer[];

const THAILAND_CENTER: [number, number] = [15.87, 100.99];

const isoDaysAgo = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};

/**
 * เลื่อนแผนที่ให้เห็นหมุดทั้งหมดเมื่อชุดข้อมูลเปลี่ยน
 *
 * ถ้าไม่ทำ ผู้ใช้กรองจนเหลือหมุดเดียวที่เชียงรายแล้วแผนที่ยังค้างอยู่ที่กรุงเทพ
 * จะเห็นเป็นแผนที่เปล่าและเข้าใจว่าไม่มีข้อมูล
 */
const FitToPoints: React.FC<{ points: MapPoint[] }> = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    const bounds = points.map((p) => [p.lat, p.lng]) as [number, number][];
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  }, [map, points]);
  return null;
};

interface Props {
  /** สถานีที่ใช้เลือกฐานข้อมูล กก. — ระดับ ฝอ./ผกก. จะเห็นทุกสถานีในกองตัวเอง */
  station: string;
  /** รายชื่อสถานีในกอง ให้เลือกกรองเจาะลงสถานีเดียวได้ */
  stations?: { station: string; name: string }[];
}

export const MapPanel: React.FC<Props> = ({ station, stations = [] }) => {
  const { user } = useAuth();
  const { units, charges } = useStationData({ charges: true });

  const [active, setActive] = useState<MapLayer[]>([...ALL_LAYERS]);
  const [start, setStart] = useState(isoDaysAgo(30));
  const [end, setEnd] = useState(isoDaysAgo(0));
  const [charge, setCharge] = useState('');
  const [unit, setUnit] = useState('');
  const [stationFilter, setStationFilter] = useState('');
  const [data, setData] = useState<MapPointsData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    if (!active.length) {
      setData({ points: [], counts: { crime: 0, checkpoint: 0, accident: 0 }, skippedInvalidCoordinates: 0 });
      return;
    }
    setBusy(true);
    setError('');
    const res = await api.getMapPoints(
      { station, start, end, layers: active, charge, unit, stationFilter },
      user?.token,
    );
    setBusy(false);
    if (res.status !== 'success' || !res.data) {
      setError(res.message || 'ดึงข้อมูลแผนที่ไม่สำเร็จ');
      return;
    }
    setData(res.data);
  };

  // โหลดครั้งแรกครั้งเดียว การกรองที่เหลือให้ผู้ใช้กดเอง ไม่ยิงทุกครั้งที่เปลี่ยนตัวเลือก
  // เพราะหนึ่งครั้งเท่ากับอ่านสามตารางจากชีต
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (layer: MapLayer) =>
    setActive((prev) => (prev.includes(layer) ? prev.filter((l) => l !== layer) : [...prev, layer]));

  const visible = useMemo(
    () => (data?.points || []).filter((p) => active.includes(p.layer)),
    [data, active],
  );

  return (
    <>
      <div className="glass-card mb-3">
        <div className="row g-2 align-items-end">
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">ตั้งแต่วันที่</label>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">ถึงวันที่</label>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          {stations.length > 0 && (
            <div className="col-12 col-md-2">
              <label className="form-label small text-white-50 mb-1">สถานี</label>
              <select className="form-select form-select-sm" value={stationFilter} onChange={(e) => setStationFilter(e.target.value)}>
                <option value="">— ทุกสถานีในกอง —</option>
                {stations.map((s) => <option key={s.station} value={s.station}>{s.name}</option>)}
              </select>
            </div>
          )}
          <div className="col-12 col-md-2">
            <label className="form-label small text-white-50 mb-1">หน่วยบริการ</label>
            <select className="form-select form-select-sm" value={unit} onChange={(e) => setUnit(e.target.value)}>
              <option value="">— ทุกหน่วย —</option>
              {units.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div className="col-12 col-md-2">
            <label className="form-label small text-white-50 mb-1">
              ฐานความผิด <span className="text-white-50">(เฉพาะชั้นจับกุม)</span>
            </label>
            <select className="form-select form-select-sm" value={charge} onChange={(e) => setCharge(e.target.value)}>
              <option value="">— ทุกฐานความผิด —</option>
              {charges.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="col-12 col-md-2">
            <button className="btn btn-info btn-sm w-100 fw-bold" onClick={load} disabled={busy}>
              {busy ? 'กำลังค้น...' : 'แสดงแผนที่'}
            </button>
          </div>
        </div>

        <div className="d-flex flex-wrap gap-2 mt-3">
          {ALL_LAYERS.map((layer) => {
            const meta = LAYER_META[layer];
            const on = active.includes(layer);
            return (
              <button
                key={layer}
                type="button"
                className="btn btn-sm"
                onClick={() => toggle(layer)}
                style={{
                  border: `1px solid ${meta.color}`,
                  color: on ? '#0b1120' : meta.color,
                  background: on ? meta.color : 'transparent',
                  fontWeight: 600,
                }}
              >
                <i className={`fa-solid ${meta.icon}`}></i> {meta.label}
                {data ? ` (${data.counts?.[layer] ?? 0})` : ''}
              </button>
            );
          })}
          <span className="small text-white-50 align-self-center ms-auto">แสดง {visible.length} จุด</span>
        </div>

        {error && <div className="alert alert-warning py-2 mt-3 mb-0 small">{error}</div>}
        {!!data?.skippedInvalidCoordinates && (
          <div className="alert alert-warning py-2 mt-3 mb-0 small">
            <i className="fa-solid fa-triangle-exclamation"></i> มี {data.skippedInvalidCoordinates} รายการ
            ที่กรอกพิกัดไว้แต่อยู่นอกกรอบประเทศไทย จึงไม่ถูกแสดงบนแผนที่ (มักเกิดจากสลับค่า
            ละติจูดกับลองจิจูด) กรุณาให้หน่วยตรวจสอบรายการเหล่านั้น
          </div>
        )}
      </div>

      <div className="glass-card p-0" style={{ height: '62vh', minHeight: 420, overflow: 'hidden' }}>
        <MapContainer center={THAILAND_CENTER} zoom={6} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitToPoints points={visible} />
          {visible.map((p) => (
            <CircleMarker
              key={`${p.layer}-${p.recordId}`}
              center={[p.lat, p.lng]}
              radius={7}
              pathOptions={{
                color: LAYER_META[p.layer].color,
                fillColor: LAYER_META[p.layer].color,
                fillOpacity: 0.75,
                weight: 1,
              }}
            >
              <Popup>
                <div style={{ minWidth: 200 }}>
                  <div className="fw-bold">{LAYER_META[p.layer].label}</div>
                  <div>{p.title}</div>
                  {p.detail && <div className="text-muted small mt-1">{p.detail}</div>}
                  <hr className="my-2" />
                  <div className="small text-muted">
                    {p.date} · {p.unit || p.station}
                    <br />
                    {p.recordId}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </>
  );
};
