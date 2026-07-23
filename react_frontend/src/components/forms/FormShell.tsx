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
        <div className="d-flex justify-content-between align-items-center mb-3">
          <button className="btn btn-sm btn-outline-info" onClick={onBack}>
            <i className="fa-solid fa-arrow-left"></i> {backLabel}
          </button>
          <h4 className="text-info m-0 text-center" style={{ flex: 1 }}>{title}</h4>
          <div style={{ width: 90 }}></div>
        </div>
        {children}
      </div>
    </div>
  );
};
