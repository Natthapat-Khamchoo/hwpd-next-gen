import React, { Suspense, lazy, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginView } from './components/common/LoginView';
import { MainMenuGrid } from './components/dashboards/MainMenuGrid';
import type { UserRole } from './types';

// Lazily loaded so the login/menu chunk stays small and ApexCharts only loads
// when a dashboard is actually opened.
const named = <T extends Record<string, any>, K extends keyof T>(loader: () => Promise<T>, key: K) =>
  lazy(() => loader().then((m) => ({ default: m[key] })));

const DailyReportForm = named(() => import('./components/forms/DailyReportForm'), 'DailyReportForm');
const CheckpointForm = named(() => import('./components/forms/CheckpointForm'), 'CheckpointForm');
const ArrestForm = named(() => import('./components/forms/ArrestForm'), 'ArrestForm');
const AccidentForm = named(() => import('./components/forms/AccidentForm'), 'AccidentForm');
const MissionForm = named(() => import('./components/forms/MissionForm'), 'MissionForm');
const MissionViewForm = named(() => import('./components/forms/MissionViewForm'), 'MissionViewForm');
const PrForm = named(() => import('./components/forms/PrForm'), 'PrForm');
const DocumentForm = named(() => import('./components/forms/DocumentForm'), 'DocumentForm');
const RoyalGuardForm = named(() => import('./components/forms/RoyalGuardForm'), 'RoyalGuardForm');
const FuelForm = named(() => import('./components/forms/FuelForm'), 'FuelForm');
const MyHistoryForm = named(() => import('./components/forms/MyHistoryForm'), 'MyHistoryForm');
const ToolsForm = named(() => import('./components/forms/ToolsForm'), 'ToolsForm');

const StationAdminDashboard = named(() => import('./components/dashboards/StationAdminDashboard'), 'StationAdminDashboard');
const HqDashboard = named(() => import('./components/dashboards/HqDashboard'), 'HqDashboard');
const CommanderDashboard = named(() => import('./components/dashboards/CommanderDashboard'), 'CommanderDashboard');
const SuperCommanderDashboard = named(() => import('./components/dashboards/SuperCommanderDashboard'), 'SuperCommanderDashboard');
const HqAdminDashboard = named(() => import('./components/dashboards/HqAdminDashboard'), 'HqAdminDashboard');

// The landing view for each role, mirroring the original showMainMenu() routing.
const roleHome = (role?: UserRole): string => {
  switch (role) {
    case 'สิบเวร':
    case 'Station_Admin':
      return 'station_admin';
    case 'Division_Admin':
      return 'hq';
    case 'Division_Commander':
      return 'commander';
    case 'Super_Commander':
      return 'super_commander';
    case 'HQ_Admin':
      return 'hq_admin';
    default:
      return 'main';
  }
};

const Loading: React.FC = () => (
  <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh' }}>
    <span className="spin" style={{ display: 'inline-block', width: 40, height: 40, border: '3px solid var(--neon-blue)', borderTopColor: 'transparent', borderRadius: '50%' }}></span>
  </div>
);

const MainContent: React.FC = () => {
  const { user } = useAuth();
  const [currentView, setCurrentView] = useState<string>('main');

  useEffect(() => {
    if (user) setCurrentView(roleHome(user.role));
  }, [user]);

  if (!user) return <LoginView />;

  const back = () => setCurrentView('main');

  const render = () => {
    switch (currentView) {
      case 'daily': return <DailyReportForm onBack={back} />;
      case 'checkpoint': return <CheckpointForm onBack={back} />;
      case 'arrest': return <ArrestForm onBack={back} />;
      case 'accident': return <AccidentForm onBack={back} />;
      case 'mission': return <MissionForm onBack={back} />;
      case 'mission_view': return <MissionViewForm onBack={back} />;
      case 'pr': return <PrForm onBack={back} />;
      case 'document': return <DocumentForm onBack={back} />;
      case 'royal_guard': return <RoyalGuardForm onBack={back} />;
      case 'fuel': return <FuelForm onBack={back} />;
      case 'history': return <MyHistoryForm onBack={back} />;
      case 'tools': return <ToolsForm onBack={back} />;
      case 'station_admin': return <StationAdminDashboard onBack={back} />;
      case 'hq': return <HqDashboard onBack={back} />;
      case 'commander': return <CommanderDashboard onBack={back} onSwitchHQ={() => setCurrentView('hq')} />;
      case 'super_commander': return <SuperCommanderDashboard onBack={back} />;
      case 'hq_admin': return <HqAdminDashboard onBack={back} />;
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
