import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { LoginView } from './components/common/LoginView';
import { MainMenuGrid } from './components/dashboards/MainMenuGrid';

// Operation Forms
import { DailyReportForm } from './components/forms/DailyReportForm';
import { CheckpointForm } from './components/forms/CheckpointForm';
import { ArrestForm } from './components/forms/ArrestForm';

// Role Dashboards
import { StationAdminDashboard } from './components/dashboards/StationAdminDashboard';
import { SuperCommanderDashboard } from './components/dashboards/SuperCommanderDashboard';

const MainContent: React.FC = () => {
  const { user } = useAuth();
  const [currentView, setCurrentView] = useState<string>('main');

  if (!user) {
    return <LoginView />;
  }

  const renderView = () => {
    switch (currentView) {
      case 'daily':
        return <DailyReportForm onBack={() => setCurrentView('main')} />;
      case 'checkpoint':
        return <CheckpointForm onBack={() => setCurrentView('main')} />;
      case 'arrest':
        return <ArrestForm onBack={() => setCurrentView('main')} />;
      case 'station_admin':
        return <StationAdminDashboard onBack={() => setCurrentView('main')} />;
      case 'division_admin':
        return <StationAdminDashboard onBack={() => setCurrentView('main')} />;
      case 'commander':
      case 'super_commander':
        return <SuperCommanderDashboard onBack={() => setCurrentView('main')} />;
      default:
        return <MainMenuGrid onSelectView={setCurrentView} />;
    }
  };

  return (
    <div className="min-h-screen pb-16">
      <Navbar onGoHome={() => setCurrentView('main')} />
      <main>{renderView()}</main>
    </div>
  );
};

export function App() {
  return (
    <AuthProvider>
      <MainContent />
    </AuthProvider>
  );
}

export default App;
