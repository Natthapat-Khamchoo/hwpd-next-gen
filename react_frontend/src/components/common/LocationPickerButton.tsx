import React, { Suspense, lazy, useState } from 'react';

/**
 * ปุ่มเปิดแผนที่ปักหมุด ใช้แทนการเรียก `LocationPickerModal` ตรง ๆ ในทุกฟอร์ม
 *
 * โหลด leaflet แบบ lazy เพราะไลบรารีกับ CSS ของมันหนักราว 150 KB และมีแค่สามฟอร์ม
 * ที่ใช้ ถ้า import ตรง ๆ ทุกคนที่แค่เปิดหน้าล็อกอินก็ต้องโหลดไปด้วย
 */
const LocationPickerModal = lazy(() =>
  import('./LocationPickerModal').then((m) => ({ default: m.LocationPickerModal })),
);

interface Props {
  lat?: string;
  lng?: string;
  title?: string;
  label?: string;
  className?: string;
  onSelect: (lat: string, lng: string) => void;
}

export const LocationPickerButton: React.FC<Props> = ({
  lat,
  lng,
  title,
  label = 'ปักหมุดบนแผนที่',
  className = 'btn btn-outline-info w-100',
  onSelect,
}) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}>
        <i className="fa-solid fa-map-location-dot"></i> {label}
      </button>
      {open && (
        <Suspense
          fallback={
            <div
              className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
              style={{ background: 'rgba(0,0,0,.75)', zIndex: 2000 }}
            >
              <span className="spinner-border text-info"></span>
            </div>
          }
        >
          <LocationPickerModal
            initialLat={lat}
            initialLng={lng}
            title={title}
            onSelect={onSelect}
            onClose={() => setOpen(false)}
          />
        </Suspense>
      )}
    </>
  );
};
