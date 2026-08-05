import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { DashboardLayout, SideItem } from './DashboardLayout';
import { PrPanel } from './hq/PrPanel';
import { PrForm } from '../forms/PrForm';

/**
 * แผงงานประชาสัมพันธ์ของฝ่าย PR ส่วนกลาง (บก.ทล.)
 *
 * ต่างจากงาน PR ที่ฝังอยู่ในหน้า ฝอ.กก. สองเรื่อง
 *
 * หนึ่ง หน้านี้มีแต่งาน PR ไม่มีเมนูอื่นเลย เพราะบัญชีนี้แตะอย่างอื่นไม่ได้จริง ๆ
 * ด่านอยู่ที่ backend (PR_ONLY_ALLOWED_PREFIXES) ไม่ใช่แค่การไม่มีปุ่มให้กด
 *
 * สอง ฝ่าย PR อยู่สถานี "00" ซึ่งไม่ใช่ กก. ไหนเลย ทุกคำขอจึงต้องบอกว่าทำงานกับกอง
 * ไหนอยู่ ไม่งั้น backend ไม่รู้ว่าต้องเปิดสเปรดชีตของใคร — ตัวเลือก กก. ด้านบน
 * จึงไม่ใช่ตัวกรองเพื่อความสะดวก แต่เป็นข้อมูลที่ขาดไม่ได้ของทุกคำขอ
 */

interface Division {
  division: string;
  name: string;
  station: string;
}

export const PrCenterDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [divisions, setDivisions] = useState<Division[]>([]);
  const [station, setStation] = useState('');
  const [error, setError] = useState('');
  const [view, setView] = useState<'news' | 'submit'>('news');

  useEffect(() => {
    api.getPrDivisions(user?.token).then((list) => {
      setDivisions(list);
      if (list.length) setStation(list[0].station);
      else setError('ยังไม่มีกองกำกับการใดตั้งค่าฐานข้อมูลไว้ กรุณาแจ้งผู้ดูแลระบบส่วนกลาง');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current = divisions.find((d) => d.station === station);

  return (
    <DashboardLayout
      bg="hqa-bg"
      variant="hqa"
      sidebar={() => (
        <>
          <div className="sidebar-header">
            <h4 className="text-white m-0" style={{ textShadow: '0 0 10px #c084fc' }}>งานประชาสัมพันธ์</h4>
            <small className="text-white-50">ฝ่าย ปชส. บก.ทล.</small>
          </div>
          <div className="sidebar-menu">
            <SideItem icon="fa-bullhorn" cls="text-warning" active={view === 'news'} onClick={() => setView('news')}>
              คลังข่าวประชาสัมพันธ์
            </SideItem>
            <SideItem icon="fa-pen-to-square" cls="text-info" active={view === 'submit'} onClick={() => setView('submit')}>
              ส่งข่าวใหม่
            </SideItem>
          </div>
          <div className="mt-auto border-top border-secondary p-3">
            <div className="small text-white-50 px-2 pb-2">
              <i className="fa-solid fa-circle-info"></i> บัญชีนี้เข้าถึงได้เฉพาะงานประชาสัมพันธ์
            </div>
            <div className="sidebar-item text-danger" onClick={logout}>
              <i className="fa-solid fa-power-off"></i> ออกจากระบบ
            </div>
          </div>
        </>
      )}
    >
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h3 className="text-white m-0">คลังข่าวประชาสัมพันธ์{current ? ` ${current.name}` : ''}</h3>
          <p className="text-white-50 small m-0">
            ยินดีต้อนรับ, <span className="text-info">{user?.fullName}</span>
          </p>
        </div>
        <div className="d-flex align-items-center gap-2">
          <label className="text-white-50 small mb-0" htmlFor="pr-division">กองกำกับการ</label>
          <select
            id="pr-division"
            className="form-select form-select-sm bg-dark text-white border-info"
            style={{ width: 180 }}
            value={station}
            onChange={(e) => setStation(e.target.value)}
            disabled={!divisions.length}
          >
            {divisions.map((d) => (
              <option key={d.station} value={d.station}>{d.name}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="alert alert-warning py-2">{error}</div>}

      {/*
        key={station} บังคับให้ PrPanel สร้างใหม่ทั้งตัวเมื่อสลับกอง
        ถ้าไม่ทำ ตารางข่าว ตัวกรอง และรายงานค้างอนุมัติของกองเดิมจะค้างอยู่บนจอ
        จนกว่าจะกดค้นหาเอง ซึ่งอ่านได้ว่าเป็นข้อมูลของกองใหม่ทั้งที่ไม่ใช่
      */}
      {station && view === 'news' && <PrPanel key={station} station={station} canDecide />}

      {/*
        ส่งข่าวเข้ากองที่เลือกไว้ด้านบน ไม่ใช่เข้าสถานีของคนกรอกซึ่งคือ "00"
        ข่าวที่ฝ่าย ปชส. ส่งเองยังเข้าคิวรออนุมัติตามปกติ ไม่ข้ามคิวแม้คนส่งจะอนุมัติได้เอง
      */}
      {station && view === 'submit' && (
        <PrForm key={station} station={station} onBack={() => setView('news')} />
      )}
    </DashboardLayout>
  );
};

export default PrCenterDashboard;
