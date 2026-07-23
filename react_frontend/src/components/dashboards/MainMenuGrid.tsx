import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import Swal from 'sweetalert2';

interface MainMenuGridProps {
  onSelectView: (viewId: string) => void;
}

const MENU_ITEMS: { id: string; icon: string; label: string }[] = [
  { id: 'daily', icon: 'fa-clipboard-list', label: 'รายงานประจำวัน' },
  { id: 'checkpoint', icon: 'fa-road-barrier', label: 'รายงานตั้งด่าน' },
  { id: 'arrest', icon: 'fa-handcuffs', label: 'รายงานจับกุม' },
  { id: 'accident', icon: 'fa-car-burst', label: 'รายงานอุบัติเหตุ' },
  { id: 'mission', icon: 'fa-bullseye', label: 'แจ้งภารกิจ' },
  { id: 'mission_view', icon: 'fa-list-check', label: 'เรียกดูภารกิจ' },
  { id: 'pr', icon: 'fa-bullhorn', label: 'การประชาสัมพันธ์' },
  { id: 'document', icon: 'fa-file-signature', label: 'บันทึกข้อความ' },
  { id: 'royal_guard', icon: 'fa-shield-halved', label: 'รายงานรับเสด็จ' },
  { id: 'fuel', icon: 'fa-gas-pump', label: 'น้ำมัน/น้ำมันเครื่อง' },
  { id: 'history', icon: 'fa-clock-rotate-left', label: 'ประวัติของฉัน' },
  { id: 'tools', icon: 'fa-toolbox', label: 'เครื่องมือการทำงาน' },
];

export const MainMenuGrid: React.FC<MainMenuGridProps> = ({ onSelectView }) => {
  const { user, logout } = useAuth();
  const role = user?.role || 'Unit_Staff';
  const showBackToAdmin = role === 'สิบเวร' || role === 'Station_Admin';

  const showChangePasswordModal = async () => {
    const { value } = await Swal.fire({
      title: '<i class="fa-solid fa-user-lock" style="color:#00f2ff"></i> เปลี่ยนรหัสผ่าน',
      html: `
        <div style="text-align:left;margin-top:12px">
          <label style="font-size:.8rem;color:#9ca3af">รหัสผ่านเดิม</label>
          <input type="password" id="oldPass" class="swal2-input" placeholder="กรอกรหัสผ่านปัจจุบัน" style="margin:.25rem 0 1rem">
          <label style="font-size:.8rem;color:#9ca3af">รหัสผ่านใหม่ (อย่างน้อย 4 ตัว)</label>
          <input type="password" id="newPass" class="swal2-input" placeholder="ตั้งรหัสผ่านใหม่" style="margin:.25rem 0 1rem">
          <label style="font-size:.8rem;color:#9ca3af">ยืนยันรหัสผ่านใหม่</label>
          <input type="password" id="confirmPass" class="swal2-input" placeholder="กรอกรหัสผ่านใหม่อีกครั้ง" style="margin:.25rem 0 0">
        </div>`,
      confirmButtonText: '<i class="fa-solid fa-save"></i> บันทึกรหัสผ่าน',
      showCancelButton: true,
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#0066ff',
      preConfirm: () => {
        const oldPass = (document.getElementById('oldPass') as HTMLInputElement)?.value;
        const newPass = (document.getElementById('newPass') as HTMLInputElement)?.value;
        const confirmPass = (document.getElementById('confirmPass') as HTMLInputElement)?.value;
        if (!oldPass || !newPass || !confirmPass) {
          Swal.showValidationMessage('กรุณากรอกข้อมูลให้ครบทุกช่อง');
          return false;
        }
        if (newPass !== confirmPass) {
          Swal.showValidationMessage('รหัสผ่านใหม่และการยืนยันไม่ตรงกัน');
          return false;
        }
        if (newPass.length < 4) {
          Swal.showValidationMessage('รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 4 ตัวอักษร');
          return false;
        }
        return { oldPass, newPass };
      },
    });

    if (!value) return;
    Swal.fire({ title: 'กำลังอัปเดตข้อมูล...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const res = await api.changePassword(user!.username, value.oldPass, value.newPass, user?.token);
      if (res.status === 'success') {
        await Swal.fire({ icon: 'success', title: 'สำเร็จ!', text: res.message || 'เปลี่ยนรหัสผ่านเรียบร้อย', confirmButtonText: 'ตกลง' });
        logout();
      } else {
        Swal.fire('ผิดพลาด', res.message || 'ไม่สามารถเปลี่ยนรหัสผ่านได้', 'error');
      }
    } catch {
      Swal.fire('ข้อผิดพลาดระบบ', 'ไม่สามารถเชื่อมต่อฐานข้อมูลได้ กรุณาลองใหม่', 'error');
    }
  };

  const confirmLogout = async () => {
    const r = await Swal.fire({
      title: 'ออกจากระบบ?',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'ออกจากระบบ',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#dc3545',
    });
    if (r.isConfirmed) logout();
  };

  return (
    <div className="d-flex align-items-start justify-content-center" style={{ minHeight: '100vh', padding: 20 }}>
      <div className="glass-card animate-fade-in" style={{ width: '100%', maxWidth: 820 }}>
        {/* Profile section */}
        <div className="profile-section">
          <div className="profile-info">
            <h5>{user?.fullName || 'กำลังโหลด...'}</h5>
            <p>
              <i className="fa-solid fa-location-dot"></i> ส.ทล.{user?.station} | รหัสหน่วย: {user?.unit} | สิทธิ์:{' '}
              {user?.role}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {showBackToAdmin && (
              <button
                className="btn-outline-round btn-outline-warning"
                onClick={() => onSelectView('station_admin')}
                title="แผงควบคุม"
              >
                <i className="fa-solid fa-chart-pie"></i> แผงควบคุม
              </button>
            )}
            <button className="btn-outline-round btn-outline-info" onClick={showChangePasswordModal} title="เปลี่ยนรหัสผ่าน">
              <i className="fa-solid fa-key"></i>
            </button>
            <button className="btn-outline-round btn-outline-danger" onClick={confirmLogout} title="ออกจากระบบ">
              <i className="fa-solid fa-power-off"></i>
            </button>
          </div>
        </div>

        <h6 style={{ marginBottom: '1rem', color: 'rgba(255,255,255,0.5)', fontWeight: 400 }}>
          <i className="fa-solid fa-bars"></i> เมนูการปฏิบัติงาน
        </h6>

        <div className="menu-grid">
          {MENU_ITEMS.map((item) => (
            <div key={item.id} className="menu-btn" onClick={() => onSelectView(item.id)}>
              <i className={`fa-solid ${item.icon}`}></i>
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
