import React, { useState } from 'react';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

/**
 * ปักหมุดบนแผนที่เพื่อดึงพิกัดใส่ฟอร์ม (requirement ข้อ 5 และ 16)
 *
 * ของเดิมมีแต่ปุ่ม "ดึงพิกัดปัจจุบัน" ซึ่งใช้ได้เฉพาะตอนที่เจ้าหน้าที่ยืนอยู่ตรงจุดนั้นพอดี
 * รายงานที่พิมพ์ย้อนหลังที่หน่วย หรืออุบัติเหตุที่เกิดคนละจุดกับที่นั่งเขียนรายงาน
 * จึงกรอกพิกัดไม่ได้เลย ต้องเปิด Google Maps อีกแท็บแล้วคัดลอกตัวเลขมาเอง
 *
 * แผนที่พื้นหลังใช้ไทล์ของ OpenStreetMap ซึ่ง **ต้องต่ออินเทอร์เน็ตออกนอกหน่วย**
 * ถ้าเครือข่ายของหน่วยบล็อก tile.openstreetmap.org แผนที่จะขึ้นเป็นพื้นเทา
 * แต่ยังปักหมุดและอ่านพิกัดได้ตามปกติ เพราะพิกัดคำนวณจากตำแหน่งที่คลิก ไม่ใช่จากภาพไทล์
 */

// leaflet อ้างไฟล์ไอคอนด้วย path ที่ bundler แก้ให้ไม่ได้ ถ้าไม่ตั้งเอง หมุดจะหายไปทั้งอัน
// (ขึ้นเป็นภาพแตก) ซึ่งเป็นอาการคลาสสิกของ leaflet + bundler ทุกตัว
L.Marker.prototype.options.icon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

/** กลางประเทศไทยโดยประมาณ ใช้เมื่อยังไม่มีพิกัดตั้งต้นและขอ GPS ไม่ได้ */
const THAILAND_CENTER: [number, number] = [15.87, 100.99];

/** ทศนิยม 6 ตำแหน่งละเอียดราวหนึ่งเมตร มากกว่านี้ไม่มีประโยชน์และอ่านยาก */
const trim = (value: number) => Number(value.toFixed(6));

interface Props {
  /** พิกัดที่ฟอร์มมีอยู่แล้ว เปิดแผนที่ค้างไว้ที่จุดนั้น */
  initialLat?: string;
  initialLng?: string;
  title?: string;
  onSelect: (lat: string, lng: string) => void;
  onClose: () => void;
}

const ClickCatcher: React.FC<{ onPick: (lat: number, lng: number) => void }> = ({ onPick }) => {
  useMapEvents({
    click: (event) => onPick(event.latlng.lat, event.latlng.lng),
  });
  return null;
};

export const LocationPickerModal: React.FC<Props> = ({
  initialLat,
  initialLng,
  title = 'ปักหมุดพิกัด',
  onSelect,
  onClose,
}) => {
  const startLat = parseFloat(initialLat || '');
  const startLng = parseFloat(initialLng || '');
  const hasStart = Number.isFinite(startLat) && Number.isFinite(startLng);

  const [pin, setPin] = useState<[number, number] | null>(hasStart ? [startLat, startLng] : null);
  const [locating, setLocating] = useState(false);
  const [note, setNote] = useState('');

  const center = pin || THAILAND_CENTER;

  const useCurrentPosition = () => {
    if (!navigator.geolocation) {
      setNote('เบราว์เซอร์นี้ไม่รองรับการดึงพิกัด GPS');
      return;
    }
    setLocating(true);
    setNote('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setPin([position.coords.latitude, position.coords.longitude]);
        setLocating(false);
      },
      () => {
        setLocating(false);
        setNote('ดึงพิกัดปัจจุบันไม่สำเร็จ กรุณาคลิกบนแผนที่เพื่อปักหมุดเอง');
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const confirm = () => {
    if (!pin) return;
    onSelect(String(trim(pin[0])), String(trim(pin[1])));
    onClose();
  };

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-start justify-content-center"
      style={{ background: 'rgba(0,0,0,.75)', zIndex: 2000, overflowY: 'auto', padding: '3vh 1rem' }}
    >
      <div className="glass-card p-4" style={{ maxWidth: 860, width: '100%' }}>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="text-white m-0">
            <i className="fa-solid fa-map-location-dot text-info"></i> {title}
          </h5>
          <button className="btn btn-sm btn-outline-light" onClick={onClose}>ปิด</button>
        </div>

        <p className="small text-white-50 mb-2">
          คลิกบนแผนที่เพื่อปักหมุด หรือลากหมุดเพื่อปรับตำแหน่งให้ตรงจุดเกิดเหตุ
        </p>

        {/* กำหนดความสูงเป็น px ตรง ๆ เพราะ leaflet ต้องรู้ขนาดตอน mount
            ถ้าใช้ % แล้วพ่อแม่ไม่มีความสูงชัดเจน แผนที่จะสูง 0 และไม่ขึ้นอะไรเลย */}
        <div style={{ height: 420, borderRadius: 10, overflow: 'hidden', border: '1px solid rgba(0,242,255,.25)' }}>
          <MapContainer center={center} zoom={hasStart ? 15 : 6} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ClickCatcher onPick={(lat, lng) => setPin([lat, lng])} />
            {pin && (
              <Marker
                position={pin}
                draggable
                eventHandlers={{
                  dragend: (event) => {
                    const { lat, lng } = event.target.getLatLng();
                    setPin([lat, lng]);
                  },
                }}
              />
            )}
          </MapContainer>
        </div>

        {note && <div className="alert alert-warning py-2 mt-3 mb-0 small">{note}</div>}

        <div className="row g-2 align-items-end mt-2">
          <div className="col-6 col-md-3">
            <label className="form-label small text-white-50 mb-1">ละติจูด</label>
            <input className="form-control form-control-sm" readOnly value={pin ? trim(pin[0]) : ''} placeholder="ยังไม่ปักหมุด" />
          </div>
          <div className="col-6 col-md-3">
            <label className="form-label small text-white-50 mb-1">ลองจิจูด</label>
            <input className="form-control form-control-sm" readOnly value={pin ? trim(pin[1]) : ''} placeholder="ยังไม่ปักหมุด" />
          </div>
          <div className="col-12 col-md-6 d-flex gap-2">
            <button type="button" className="btn btn-outline-info btn-sm flex-grow-1" onClick={useCurrentPosition} disabled={locating}>
              <i className="fa-solid fa-location-crosshairs"></i> {locating ? 'กำลังหาพิกัด...' : 'ใช้พิกัดปัจจุบัน'}
            </button>
            <button type="button" className="btn btn-info btn-sm fw-bold flex-grow-1" onClick={confirm} disabled={!pin}>
              <i className="fa-solid fa-check"></i> ใช้พิกัดนี้
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LocationPickerModal;
