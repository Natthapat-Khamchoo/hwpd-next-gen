import React, { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { formatPreviewDate } from '../../utils/formHelpers';
import type { NationalCheckpoint, NationalCheckpointsData } from '../../types';

/**
 * แผนที่จุดตั้งด่านทั่วประเทศบนหน้าภาพรวมของ ผบก.ทล.
 *
 * หมุดเขียว = ด่านที่ยังตั้งอยู่ ณ เวลาที่ backend ตรวจ หมุดเทา = เลิกด่านไปแล้วหรือ
 * ยังไม่ถึงเวลาเริ่ม สถานะมาจากช่วงเวลาที่เจ้าหน้าที่กรอกในรายงานตั้งด่าน ไม่ใช่เดา
 * จากวันที่ของรายงาน
 *
 * ใช้ `CircleMarker` ตามเหตุผลเดียวกับ MapPanel — วาดลง canvas layer เดียว ไม่สร้าง
 * DOM element ต่อหมุด
 */

const THAILAND_CENTER: [number, number] = [15.87, 100.99];

const ACTIVE_COLOR = '#22c55e';
const CLOSED_COLOR = '#6b7280';

/** เลื่อนแผนที่ให้เห็นหมุดทั้งหมดเมื่อชุดข้อมูลเปลี่ยน */
const FitToPoints: React.FC<{ points: NationalCheckpoint[] }> = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    map.fitBounds(points.map((p) => [p.lat, p.lng]) as [number, number][], { padding: [40, 40], maxZoom: 11 });
  }, [map, points]);
  return null;
};

export const NationalCheckpointMap: React.FC = () => {
  const { user } = useAuth();
  const [data, setData] = useState<NationalCheckpointsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // ค่าเริ่มต้นโชว์เฉพาะด่านที่ยังตั้งอยู่ เพราะนั่นคือคำถามที่ผู้บังคับการเปิดหน้านี้มาถาม
  const [onlyActive, setOnlyActive] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    const res = await api.getNationalCheckpoints(user?.token);
    setLoading(false);
    if (res.status === 'success' && res.data) setData(res.data);
    else setError(res.message || 'ดึงจุดตั้งด่านไม่สำเร็จ');
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shown = useMemo(
    () => (data ? data.points.filter((p) => (onlyActive ? p.active : true)) : []),
    [data, onlyActive],
  );

  return (
    <div className="glass-card w-100 mb-4">
      <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <h5 className="text-warning m-0">
          <i className="fa-solid fa-map-location-dot"></i> จุดตั้งด่านทั่วประเทศ
        </h5>
        <div className="d-flex flex-wrap align-items-center gap-2">
          <span className="badge" style={{ background: ACTIVE_COLOR }}>
            ตั้งอยู่ {data?.activeCount ?? 0}
          </span>
          <span className="badge" style={{ background: CLOSED_COLOR }}>
            เลิกแล้ว {(data?.totalCount ?? 0) - (data?.activeCount ?? 0)}
          </span>
          <button
            type="button"
            className={`btn btn-sm ${onlyActive ? 'btn-success' : 'btn-outline-secondary'}`}
            onClick={() => setOnlyActive((v) => !v)}
          >
            {onlyActive ? 'แสดงเฉพาะที่ตั้งอยู่' : 'แสดงทั้งหมด'}
          </button>
          <button type="button" className="btn btn-sm btn-outline-warning" onClick={load} disabled={loading}>
            <i className="fa-solid fa-rotate"></i> รีเฟรช
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      {data && data.unavailableDivisions.length > 0 && (
        <div className="alert alert-warning py-2 small">
          อ่านฐานข้อมูลของ กก.{data.unavailableDivisions.join(', กก.')} ไม่ได้ในรอบนี้ ด่านของกองดังกล่าวจึงยังไม่ขึ้นบนแผนที่
        </div>
      )}

      <div style={{ height: 460, borderRadius: 12, overflow: 'hidden' }}>
        <MapContainer center={THAILAND_CENTER} zoom={6} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitToPoints points={shown} />
          {shown.map((p) => (
            <CircleMarker
              key={p.recordId}
              center={[p.lat, p.lng]}
              radius={p.active ? 9 : 6}
              pathOptions={{
                color: p.active ? ACTIVE_COLOR : CLOSED_COLOR,
                fillColor: p.active ? ACTIVE_COLOR : CLOSED_COLOR,
                fillOpacity: p.active ? 0.85 : 0.4,
                weight: p.active ? 2 : 1,
              }}
            >
              <Popup>
                <div style={{ minWidth: 200 }}>
                  <div className="fw-bold">{p.title}</div>
                  <div className="small">
                    {p.divName} · {p.unit || p.station}
                  </div>
                  <div className="small">{p.detail}</div>
                  {p.start && p.end && (
                    <div className="small mt-1">
                      ตั้งแต่ {formatPreviewDate(p.start)}
                      <br />
                      ถึง {formatPreviewDate(p.end)}
                    </div>
                  )}
                  <div className="small mt-1" style={{ color: p.active ? ACTIVE_COLOR : CLOSED_COLOR }}>
                    {p.active ? 'ตั้งอยู่' : 'เลิกด่านแล้ว'}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="small text-white-50 mt-2">
        {loading ? 'กำลังโหลด...' : `ข้อมูล ณ ${data?.checkedAt ? formatPreviewDate(data.checkedAt) : '-'} · แสดง ${shown.length} จุด`}
      </div>
    </div>
  );
};
