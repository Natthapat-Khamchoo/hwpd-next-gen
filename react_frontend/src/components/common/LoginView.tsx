import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import Swal from 'sweetalert2';

export const LoginView: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const doLogin = async () => {
    if (!username || !password) {
      Swal.fire('แจ้งเตือน', 'กรุณากรอกข้อมูลให้ครบถ้วน', 'warning');
      return;
    }

    setLoading(true);
    try {
      const res = await api.login(username, password);
      if (res.status === 'success' && res.user) {
        login(res.user);
      } else {
        Swal.fire('เข้าสู่ระบบไม่สำเร็จ', res.message || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error');
      }
    } catch (err: any) {
      Swal.fire('ข้อผิดพลาดระบบ', 'ไม่สามารถเชื่อมต่อฐานข้อมูลได้ โปรดลองอีกครั้ง', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doLogin();
  };

  return (
    <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh', padding: 20 }}>
      <form className="glass-card login-card animate-fade-in" style={{ width: '100%', maxWidth: 400 }} onSubmit={handleSubmit}>
        <div className="title-area">
          <h2>HWPD NEXT GEN</h2>
          <p style={{ color: '#6edff6', fontSize: '0.85rem', margin: '6px 0 0' }}>
            ระบบปฏิบัติการ กองบังคับการตำรวจทางหลวง
          </p>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <input
            type="text"
            className="form-control"
            placeholder="Username"
            value={username}
            autoComplete="username"
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <input
            type="password"
            className="form-control"
            placeholder="Password"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button type="submit" className="btn-primary-custom" disabled={loading}>
          เข้าสู่ระบบ <i className="fa-solid fa-right-to-bracket"></i>
        </button>

        {loading && (
          <div style={{ textAlign: 'center', marginTop: '15px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '16px',
                height: '16px',
                border: '2px solid #6edff6',
                borderTopColor: 'transparent',
                borderRadius: '50%',
                verticalAlign: 'middle',
              }}
              className="spin"
            ></span>
            <span style={{ marginLeft: '8px', fontSize: '0.85rem' }}>กำลังตรวจสอบ...</span>
          </div>
        )}
      </form>
    </div>
  );
};
