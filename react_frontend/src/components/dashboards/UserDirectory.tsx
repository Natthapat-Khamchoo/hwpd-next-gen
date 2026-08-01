import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import Swal from 'sweetalert2';

/**
 * ทำเนียบผู้ใช้งานของ บก. — แก้ได้เฉพาะชื่อจริงกับเบอร์โทร
 *
 * ทำขึ้นเพื่องานเติมชื่อบัญชีเจ้าหน้าที่ผู้ปฏิบัติที่สร้างไว้เป็น placeholder ชื่อขึ้นต้น
 * ด้วย "(รอระบุชื่อ)" และไปโผล่ใน dropdown ผู้รายงานตามที่ตารางออกแบบไว้ (1 แถว =
 * เจ้าหน้าที่ 1 นาย) จนกว่าจะเติมชื่อจริง
 *
 * ตั้งใจไม่ให้แก้ Role กับ Station_ID จากหน้านี้ สองช่องนั้นเปลี่ยนสิทธิ์และปลายทาง
 * ที่รายงานจะถูกเขียนลง ฝั่ง API ก็ปฏิเสธไว้อีกชั้น
 */

const PLACEHOLDER = '(รอระบุชื่อ)';

export const UserDirectory: React.FC = () => {
  const { user } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [onlyPlaceholder, setOnlyPlaceholder] = useState(false);
  const [saving, setSaving] = useState('');

  const load = async () => {
    setLoading(true);
    setRows(await api.getAllUsers(user?.token));
    setLoading(false);
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const placeholderCount = useMemo(
    () => rows.filter((r) => String(r.fullName || '').startsWith(PLACEHOLDER)).length,
    [rows],
  );

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (onlyPlaceholder && !String(r.fullName || '').startsWith(PLACEHOLDER)) return false;
      if (!needle) return true;
      return ['username', 'fullName', 'station', 'unit', 'role', 'phone']
        .some((k) => String(r[k] || '').toLowerCase().includes(needle));
    });
  }, [rows, q, onlyPlaceholder]);

  const edit = async (row: any) => {
    const isPlaceholder = String(row.fullName || '').startsWith(PLACEHOLDER);
    const { value } = await Swal.fire({
      title: `แก้ข้อมูล ${row.username}`,
      html:
        `<div style="text-align:left">
           <label style="font-size:.8rem;color:#9ca3af">ยศ ชื่อ สกุล</label>
           <input id="sw-name" class="swal2-input" style="margin:.25rem 0 .75rem" value="${isPlaceholder ? '' : String(row.fullName || '').replace(/"/g, '&quot;')}" placeholder="เช่น ด.ต.สมชาย ใจดี">
           <label style="font-size:.8rem;color:#9ca3af">เบอร์โทร</label>
           <input id="sw-phone" class="swal2-input" style="margin:.25rem 0 0" value="${String(row.phone || '').replace(/"/g, '&quot;')}" placeholder="08xxxxxxxx">
           <p style="font-size:.75rem;color:#6b7280;margin:.75rem 0 0">สังกัดและสิทธิ์แก้จากหน้านี้ไม่ได้</p>
         </div>`,
      focusConfirm: false,
      showCancelButton: true,
      confirmButtonText: 'บันทึก',
      cancelButtonText: 'ยกเลิก',
      preConfirm: () => {
        const name = (document.getElementById('sw-name') as HTMLInputElement)?.value.trim();
        const phone = (document.getElementById('sw-phone') as HTMLInputElement)?.value.trim();
        if (!name) {
          Swal.showValidationMessage('กรุณากรอกชื่อ');
          return false;
        }
        return { name, phone };
      },
    });
    if (!value) return;

    setSaving(row.username);
    const res = await api.updateUserProfile(row.username, { fullName: value.name, phone: value.phone }, user?.token);
    setSaving('');
    if (res.status !== 'success') return Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');

    setRows((prev) => prev.map((r) => (r.username === row.username ? { ...r, fullName: value.name, phone: value.phone } : r)));
    Swal.fire('บันทึกแล้ว', res.message || '', 'success');
  };

  if (loading) return <div className="glass-card w-100 p-5 text-center text-white-50">กำลังโหลดทำเนียบผู้ใช้...</div>;

  return (
    <div className="glass-card w-100 p-4">
      <div className="d-flex flex-column flex-md-row gap-2 align-items-md-center mb-3">
        <input className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 320 }}
               placeholder="ค้นหา ชื่อ / username / หน่วย / เบอร์" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className={`btn btn-sm ${onlyPlaceholder ? 'btn-warning' : 'btn-outline-warning'}`}
                onClick={() => setOnlyPlaceholder((v) => !v)}>
          เฉพาะที่ยังไม่ระบุชื่อ ({placeholderCount})
        </button>
        <button className="btn btn-sm btn-outline-info" onClick={load}><i className="fa-solid fa-rotate"></i></button>
        <span className="text-white-50 small ms-md-auto">แสดง {shown.length} จาก {rows.length} บัญชี</span>
      </div>

      <div className="table-responsive" style={{ maxHeight: '60vh' }}>
        <table className="table table-sc table-bordered align-middle">
          <thead><tr><th>Username</th><th>ยศ ชื่อ สกุล</th><th>สังกัด</th><th>สิทธิ์</th><th>เบอร์โทร</th><th></th></tr></thead>
          <tbody>
            {shown.map((r) => {
              const isPlaceholder = String(r.fullName || '').startsWith(PLACEHOLDER);
              return (
                <tr key={r.username}>
                  <td className="fw-bold">{r.username}</td>
                  <td className={isPlaceholder ? 'text-warning' : 'text-white'}>{r.fullName || '-'}</td>
                  <td className="text-white-50 small">{r.station} {r.unit}</td>
                  <td className="text-white-50 small">{r.role}</td>
                  <td className="text-white-50 small">{r.phone || '-'}</td>
                  <td>
                    <button className="btn btn-sm btn-outline-light" disabled={saving === r.username}
                            onClick={() => edit(r)}>
                      {saving === r.username ? '...' : 'แก้ไข'}
                    </button>
                  </td>
                </tr>
              );
            })}
            {!shown.length && <tr><td colSpan={6} className="text-center text-white-50 py-4">ไม่พบบัญชีที่ตรงกับที่ค้นหา</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};
