import React, { useState } from 'react';

interface DashboardLayoutProps {
  /** Sidebar accent: '' = cyan, 'sc' = gold, 'hqa' = purple. */
  variant?: '' | 'sc' | 'hqa';
  /** Wrapper background class (e.g. 'hq-bg', 'sc-bg', 'hqa-bg'). */
  bg?: string;
  /** Sidebar content; receives close() to dismiss the mobile drawer on navigation. */
  sidebar: (close: () => void) => React.ReactNode;
  children: React.ReactNode;
}

/** Dashboard shell with a responsive sidebar that becomes an off-canvas drawer on mobile. */
export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ variant = '', bg = 'hq-bg', sidebar, children }) => {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <div className={`dashboard-wrapper ${bg} animate-fade-in`}>
      <button className="dash-hamburger" onClick={() => setOpen(true)} aria-label="เปิดเมนู">
        <i className="fa-solid fa-bars"></i>
      </button>
      <div className={`dash-overlay ${open ? 'show' : ''}`} onClick={close}></div>
      <aside className={`dash-sidebar ${variant} ${open ? 'show' : ''}`}>{sidebar(close)}</aside>
      <main className="main-content">{children}</main>
    </div>
  );
};

interface SideItemProps {
  icon: string;
  active?: boolean;
  cls?: string;
  badge?: number;
  onClick: () => void;
  children: React.ReactNode;
}

/** A single sidebar menu row (module-scope → no remount / focus issues). */
export const SideItem: React.FC<SideItemProps> = ({ icon, active, cls = '', badge, onClick, children }) => (
  <div className={`sidebar-item ${cls} ${active ? 'active' : ''}`} onClick={onClick}>
    <i className={`fa-solid ${icon}`}></i> {children}
    {badge ? <span className="badge bg-danger ms-auto rounded-pill">{badge}</span> : null}
  </div>
);
