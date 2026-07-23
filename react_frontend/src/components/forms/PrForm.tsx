import React from 'react';
import { FormShell } from './FormShell';

export const PrForm: React.FC<{ onBack: () => void }> = ({ onBack }) => (
  <FormShell title="การประชาสัมพันธ์" onBack={onBack} maxWidth={900}>
    <div className="glass-card w-100 text-center py-5">
      <i className="fa-solid fa-bullhorn text-warning mb-3" style={{ fontSize: '3rem' }}></i>
      <h5 className="text-white mb-2">ระบบการประชาสัมพันธ์</h5>
      <p className="text-white-50 mb-0">อยู่ระหว่างการพัฒนา จะเปิดใช้งานเร็ว ๆ นี้</p>
    </div>
  </FormShell>
);
