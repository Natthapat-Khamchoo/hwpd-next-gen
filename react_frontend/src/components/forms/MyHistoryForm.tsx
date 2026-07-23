import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { FormShell } from './FormShell';
import { loadingModal } from '../../utils/formHelpers';
import Swal from 'sweetalert2';

export const MyHistoryForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const [items, setItems] = useState<any[] | null>(null);

  const fetchHistory = async () => {
    setItems(null);
    const res = await api.getMyPendingItems(user?.username || '');
    setItems(res.status === 'success' ? res.data : []);
  };

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancelItem = async (sheetName: string, recordId: string) => {
    const r = await Swal.fire({
      title: 'ต้องการยกเลิกรายงานนี้?',
      text: 'รายการนี้จะถูกลบทิ้ง เพื่อให้คุณไปกรอกใหม่ ยืนยันหรือไม่?',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#d33',
      cancelButtonColor: '#6c757d',
      confirmButtonText: 'ยืนยันลบทิ้ง',
      cancelButtonText: 'ปิด',
    });
    if (!r.isConfirmed) return;
    loadingModal('กำลังยกเลิก...');
    const res = await api.cancelRecord(sheetName, recordId, user?.username || '', user?.token);
    if (res.status === 'success') {
      await Swal.fire('สำเร็จ!', res.message || 'ยกเลิกรายการเรียบร้อย', 'success');
      fetchHistory();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'ยกเลิกไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="ประวัติการส่งของฉัน" onBack={onBack} maxWidth={900}>
      <div className="glass-card w-100 p-3 p-md-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="text-info m-0">รายการที่รอแอดมินตรวจสอบ (Pending)</h5>
          <button className="btn btn-sm btn-outline-info" onClick={fetchHistory}><i className="fa-solid fa-rotate"></i> รีเฟรช</button>
        </div>
        <div className="alert small mb-3" style={{ background: 'rgba(0, 242, 255, 0.05)', border: '1px solid rgba(0, 242, 255, 0.2)', color: '#a0aec0', borderRadius: 8 }}>
          <i className="fa-solid fa-circle-info text-info"></i> หากพบว่ากรอกข้อมูลผิดพลาด คุณสามารถกดเข้าไปตรวจสอบและกดปุ่ม <b className="text-danger">"ยกเลิกรายการ"</b> ก่อนที่สิบเวรจะทำการอนุมัติได้ เพื่อนำไปกรอกใหม่
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle" style={{ color: '#fff' }}>
            <thead>
              <tr>
                <th style={{ color: 'var(--neon-blue)' }}>เวลาส่งรายงาน</th>
                <th style={{ color: 'var(--neon-blue)' }}>หมวดหมู่รายงาน</th>
                <th className="text-center" style={{ color: 'var(--neon-blue)' }}>จัดการ</th>
              </tr>
            </thead>
            <tbody>
              {items === null && (
                <tr><td colSpan={3} className="text-center text-white-50 py-4"><span className="spinner-border spinner-border-sm text-info me-2"></span>กำลังค้นหาประวัติของคุณ...</td></tr>
              )}
              {items && items.length === 0 && (
                <tr><td colSpan={3} className="text-center text-success py-4"><i className="fa-solid fa-check-circle fs-3 mb-2"></i><br />ไม่มีรายการค้างตรวจ (ข้อมูลของคุณถูกอนุมัติหมดแล้ว)</td></tr>
              )}
              {items && items.map((it, i) => (
                <tr key={i}>
                  <td className="small text-white-50">{it.timestamp}</td>
                  <td>
                    <div className="fw-bold text-white"><i className={`fa-solid ${it.icon || 'fa-file'} text-info`}></i> {it.formType}</div>
                    <small className="text-secondary">Ref: {it.recordId}</small>
                  </td>
                  <td className="text-center">
                    <button className="btn btn-sm btn-outline-danger w-100" onClick={() => cancelItem(it.sheetName, it.recordId)}>
                      <i className="fa-solid fa-trash"></i> ยกเลิกรายการ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </FormShell>
  );
};
