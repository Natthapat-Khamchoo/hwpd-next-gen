import React, { Suspense, lazy, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginView } from './components/common/LoginView';
import { MainMenuGrid } from './components/dashboards/MainMenuGrid';
import { canUseMainMenu, roleHome } from './utils/roles';

// Lazily loaded so the login/menu chunk stays small and ApexCharts only loads
// when a dashboard is actually opened.
//
// ทุกครั้งที่ deploy ใหม่ ชื่อไฟล์ chunk เปลี่ยน (มี hash ต่อท้าย) ของเก่าถูกลบจาก CDN
// เจ้าหน้าที่ที่เปิดหน้าค้างไว้ตั้งแต่ก่อน deploy จะยังถือรายชื่อ chunk ชุดเก่าอยู่ พอกด
// เข้าหน้าที่ยังไม่เคยโหลด จะได้ 404 แล้วเจอจอขาวเปล่า ๆ โดยไม่มีข้อความอะไรเลย
// (เจอมาแล้วตอนไล่ทดสอบ — หน้า ผบก. ขาวทั้งหน้า console ขึ้น "Failed to fetch
// dynamically imported module")
//
// โหลดใหม่หนึ่งครั้งก็ได้ไฟล์ชุดใหม่ครบ ใช้ sessionStorage กันไม่ให้วนซ้ำถ้าโหลดแล้ว
// ยังพัง ซึ่งแปลว่าเป็นปัญหาอื่นและควรปล่อยให้ error ขึ้นตามจริง
const RELOAD_FLAG = 'hwpd:chunk-reloaded';

const named = <T extends Record<string, any>, K extends keyof T>(loader: () => Promise<T>, key: K) =>
  lazy(() =>
    loader()
      .then((m) => {
        sessionStorage.removeItem(RELOAD_FLAG);
        return { default: m[key] };
      })
      .catch((error) => {
        if (sessionStorage.getItem(RELOAD_FLAG)) throw error;
        sessionStorage.setItem(RELOAD_FLAG, '1');
        window.location.reload();
        // คืน promise ที่ไม่ resolve เพื่อให้ Suspense ค้างที่ spinner ระหว่างรอโหลดใหม่
        // ถ้า throw ตรงนี้ผู้ใช้จะเห็นจอ error แวบหนึ่งก่อนหน้าจะรีเฟรช
        return new Promise<never>(() => {});
      }),
  );

const DailyReportForm = named(() => import('./components/forms/DailyReportForm'), 'DailyReportForm');
const CheckpointForm = named(() => import('./components/forms/CheckpointForm'), 'CheckpointForm');
const ArrestForm = named(() => import('./components/forms/ArrestForm'), 'ArrestForm');
const AccidentForm = named(() => import('./components/forms/AccidentForm'), 'AccidentForm');
const MissionForm = named(() => import('./components/forms/MissionForm'), 'MissionForm');
const MissionViewForm = named(() => import('./components/forms/MissionViewForm'), 'MissionViewForm');
const PrForm = named(() => import('./components/forms/PrForm'), 'PrForm');
const DocumentForm = named(() => import('./components/forms/DocumentForm'), 'DocumentForm');
const OverweightForm = named(() => import('./components/forms/OverweightForm'), 'OverweightForm');
const RoyalGuardForm = named(() => import('./components/forms/RoyalGuardForm'), 'RoyalGuardForm');
const FuelForm = named(() => import('./components/forms/FuelForm'), 'FuelForm');
const MyHistoryForm = named(() => import('./components/forms/MyHistoryForm'), 'MyHistoryForm');
const ToolsForm = named(() => import('./components/forms/ToolsForm'), 'ToolsForm');

const StationAdminDashboard = named(() => import('./components/dashboards/StationAdminDashboard'), 'StationAdminDashboard');
const HqDashboard = named(() => import('./components/dashboards/HqDashboard'), 'HqDashboard');
const CommanderDashboard = named(() => import('./components/dashboards/CommanderDashboard'), 'CommanderDashboard');
const SuperCommanderDashboard = named(() => import('./components/dashboards/SuperCommanderDashboard'), 'SuperCommanderDashboard');
const HqAdminDashboard = named(() => import('./components/dashboards/HqAdminDashboard'), 'HqAdminDashboard');


const Loading: React.FC = () => (
  <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh' }}>
    <span className="spin" style={{ display: 'inline-block', width: 40, height: 40, border: '3px solid var(--neon-blue)', borderTopColor: 'transparent', borderRadius: '50%' }}></span>
  </div>
);

/**
 * หน่วยที่กำลังเปิดดูอยู่ เมื่อผู้บริหารเจาะลึกลงหน่วยอื่น
 *
 * ของเดิมทำด้วยการเขียนทับ userData.station ใน localStorage ชั่วคราวแล้วโหลดหน้าใหม่
 * (scSwitchToDivision / cmdSwitchToStation) ที่นี่เก็บเป็น state แล้วส่งเป็น prop แทน
 * ได้พฤติกรรมเดียวกันโดยไม่ต้องแก้ตัวตนของคนที่ล็อกอินอยู่ ซึ่งถ้าพลาดคืนค่าไม่ทัน
 * จะทำให้สิทธิ์และหน่วยของเจ้าตัวเพี้ยนไปทั้ง session
 */
interface ViewAs { station: string; label: string; from: string }

const MainContent: React.FC = () => {
  const { user } = useAuth();
  const [currentView, setCurrentView] = useState<string>('main');
  // เก็บเป็น stack เพราะเจาะได้สองชั้น (ผบก. -> กก. -> สถานี) กดกลับจากสถานีต้องได้ กก.
  // ที่กำลังดูอยู่ ไม่ใช่ กก. ของตัวเอง
  const [viewStack, setViewStack] = useState<ViewAs[]>([]);
  // ผู้กำกับการกดเข้าหน้า ฝอ. จากเมนูตัวเอง ต้องมีทางกลับ ของเดิมสลับป้ายปุ่มในเมนูข้าง
  // ของหน้า ฝอ. เป็น "กลับหน้าผู้กำกับการ" ระหว่างที่อยู่ในโหมดนี้
  const [hqFromCommander, setHqFromCommander] = useState(false);
  const viewAs = viewStack.length ? viewStack[viewStack.length - 1] : null;

  const drillTo = (view: string, station: string, label: string) => {
    setViewStack((s) => [...s, { station, label, from: currentView }]);
    setCurrentView(view);
  };
  const exitView = () => {
    const top = viewStack[viewStack.length - 1];
    setViewStack((s) => s.slice(0, -1));
    setCurrentView(top?.from || roleHome(user?.role));
  };

  useEffect(() => {
    if (user) setCurrentView(roleHome(user.role));
  }, [user]);

  if (!user) return <LoginView />;

  // ระดับ บก. ไม่มีเมนูการปฏิบัติงานให้กลับไป ปุ่มย้อนกลับจึงพากลับแผงควบคุมของตัวเอง
  // ไม่ใช่ 'main' ตายตัว ไม่งั้นกดครั้งเดียวก็หลุดไปหน้าเมนูที่ของเดิมไม่เคยให้เห็น
  const back = () => setCurrentView(canUseMainMenu(user.role) ? 'main' : roleHome(user.role));

  // กันไว้อีกชั้น เผื่อมีทางไหนพา currentView มาเป็น 'main' ได้อีก และกันเมนูแวบ
  // ให้เห็นหนึ่งเฟรมก่อน useEffect จะตั้งค่า เพราะ state ตั้งต้นเป็น 'main'
  const view = currentView === 'main' && !canUseMainMenu(user.role) ? roleHome(user.role) : currentView;

  const render = () => {
    switch (view) {
      case 'daily': return <DailyReportForm onBack={back} />;
      case 'checkpoint': return <CheckpointForm onBack={back} />;
      case 'arrest': return <ArrestForm onBack={back} />;
      case 'accident': return <AccidentForm onBack={back} />;
      case 'mission': return <MissionForm onBack={back} />;
      case 'mission_view': return <MissionViewForm onBack={back} />;
      case 'pr': return <PrForm onBack={back} />;
      case 'document': return <DocumentForm onBack={back} />;
      case 'overweight': return <OverweightForm onBack={back} />;
      case 'royal_guard': return <RoyalGuardForm onBack={back} />;
      case 'fuel': return <FuelForm onBack={back} />;
      case 'history': return <MyHistoryForm onBack={back} />;
      case 'tools': return <ToolsForm onBack={back} />;
      case 'station_admin': return (
        <StationAdminDashboard
          onBack={back}
          viewStation={viewAs?.station}
          onExitView={viewAs ? exitView : undefined}
        />
      );
      case 'hq': return (
        <HqDashboard
          onBack={back}
          onBackToCommander={hqFromCommander
            ? () => { setHqFromCommander(false); setCurrentView('commander'); }
            : undefined}
        />
      );
      case 'commander': return (
        <CommanderDashboard
          onBack={back}
          onSwitchHQ={() => { setHqFromCommander(true); setCurrentView('hq'); }}
          viewStation={viewAs?.station}
          viewLabel={viewAs?.label}
          onExitView={viewAs ? exitView : undefined}
          onViewStation={(id, label) => drillTo('station_admin', id, label)}
        />
      );
      case 'super_commander': return (
        <SuperCommanderDashboard onViewDivision={(station, label) => drillTo('commander', station, label)} />
      );
      case 'hq_admin': return <HqAdminDashboard />;
      default: return <MainMenuGrid onSelectView={setCurrentView} />;
    }
  };

  return <Suspense fallback={<Loading />}>{render()}</Suspense>;
};

export function App() {
  return (
    <AuthProvider>
      <MainContent />
    </AuthProvider>
  );
}

export default App;
