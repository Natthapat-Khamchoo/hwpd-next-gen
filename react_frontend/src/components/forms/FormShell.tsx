import React from 'react';

interface FormShellProps {
  title: string;
  onBack: () => void;
  backLabel?: string;
  maxWidth?: number;
  children: React.ReactNode;
}

/** Faithful port of the form header: [← back]  <title>  [spacer], on a centered page. */
export const FormShell: React.FC<FormShellProps> = ({ title, onBack, backLabel = 'กลับเมนูหลัก', maxWidth = 800, children }) => {
  return (
    <div className="d-flex justify-content-center align-items-start animate-fade-in" style={{ minHeight: '100vh', padding: '24px 16px 60px' }}>
      <div style={{ width: '100%', maxWidth }}>
        <div className="d-flex justify-content-between align-items-center mb-3 gap-2">
          <button className="btn btn-sm btn-outline-info flex-shrink-0" onClick={onBack}>
            <i className="fa-solid fa-arrow-left"></i> <span className="d-none d-sm-inline">{backLabel}</span>
          </button>
          <h4 className="text-info m-0 text-center flex-grow-1" style={{ fontSize: 'clamp(1rem, 4vw, 1.4rem)' }}>{title}</h4>
          <div className="flex-shrink-0" style={{ width: 40 }}></div>
        </div>
        {children}
      </div>
    </div>
  );
};
