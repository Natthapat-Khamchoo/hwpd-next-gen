import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginView } from './components/common/LoginView';
import { MainMenuGrid } from './components/dashboards/MainMenuGrid';
import type { UserRole } from './types';

// Operation Forms
import { DailyReportForm } from './components/forms/DailyReportForm';
import { CheckpointForm } from './components/forms/CheckpointForm';
import { ArrestForm } from './components/forms/ArrestForm';
import { AccidentForm } from './components/forms/AccidentForm';
import { MissionForm } from './components/forms/MissionForm';
import { MissionViewForm } from './components/forms/MissionViewForm';
import { PrForm } from './components/forms/PrForm';
import { DocumentForm } from './components/forms/DocumentForm';
import { RoyalGuardForm } from './components/forms/RoyalGuardForm';
import { FuelForm } from './components/forms/FuelForm';
import { MyHistoryForm } from './components/forms/MyHistoryForm';
import { ToolsForm } from './components/forms/ToolsForm';

// Role Dashboards
import { StationAdminDashboard } from './components/dashboards/StationAdminDashboard';
import { HqDashboard } from './components/dashboards/HqDashboard';
import { CommanderDashboard } from './components/dashboards/CommanderDashboard';
import { SuperCommanderDashboard } from './components/dashboards/SuperCommanderDashboard';
import { HqAdminDashboard } from './components/dashboards/HqAdminDashboard';

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

const MainContent: React.FC = () => {
  const { user } = useAuth();
  const [currentView, setCurrentView] = useState<string>('main');

  useEffect(() => {
    if (user) setCurrentView(roleHome(user.role));
  }, [user]);

  if (!user) return <LoginView />;

  const back = () => setCurrentView('main');

  switch (currentView) {
    case 'daily':
      return <DailyReportForm onBack={back} />;
    case 'checkpoint':
      return <CheckpointForm onBack={back} />;
    case 'arrest':
      return <ArrestForm onBack={back} />;
    case 'accident':
      return <AccidentForm onBack={back} />;
    case 'mission':
      return <MissionForm onBack={back} />;
    case 'mission_view':
      return <MissionViewForm onBack={back} />;
    case 'pr':
      return <PrForm onBack={back} />;
    case 'document':
      return <DocumentForm onBack={back} />;
    case 'royal_guard':
      return <RoyalGuardForm onBack={back} />;
    case 'fuel':
      return <FuelForm onBack={back} />;
    case 'history':
      return <MyHistoryForm onBack={back} />;
    case 'tools':
      return <ToolsForm onBack={back} />;
    case 'station_admin':
      return <StationAdminDashboard onBack={back} />;
    case 'hq':
      return <HqDashboard onBack={back} />;
    case 'commander':
      return <CommanderDashboard onBack={back} onSwitchHQ={() => setCurrentView('hq')} />;
    case 'super_commander':
      return <SuperCommanderDashboard onBack={back} />;
    case 'hq_admin':
      return <HqAdminDashboard onBack={back} />;
    default:
      return <MainMenuGrid onSelectView={setCurrentView} />;
  }
};

export function App() {
  return (
    <AuthProvider>
      <MainContent />
    </AuthProvider>
  );
}

export default App;
