import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { API_BASE_URL } from '../../services/api';
import Swal from 'sweetalert2';

/**
 * ออกรายงานตามแบบฟอร์มเป็นไฟล์ Excel
 *
 * รายการที่ออกได้มาจากฝั่ง API (report_export_service.SUPPORTED) ไม่ได้ฮาร์ดโค้ดไว้
 * ที่นี่ จะได้ไม่ต้องแก้สองที่เวลาเพิ่มแบบฟอร์ม
 *
 * ดาวน์โหลดผ่าน fetch แล้วสร้าง blob เอง เพราะ endpoint ต้องส่ง header x-token
 * ซึ่ง <a download> ธรรมดาแนบไปไม่ได้
 */

const firstOfWeek = () => {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // จันทร์ของสัปดาห์นี้
  return d.toISOString().split('T')[0];
};
const today = () => new Date().toISOString().split('T')[0];

interface Report { reportKey: string; title: string; cadence: string }

export const ReportExportPanel: React.FC<{ reports: Report[] }> = ({ reports }) => {
  const { user } = useAuth();
  const [start, setStart] = useState(firstOfWeek());
  const [end, setEnd] = useState(today());
  const [busy, setBusy] = useState('');

  const download = async (report: Report) => {
    setBusy(report.reportKey);
    try {
      const q = new URLSearchParams({ reportKey: report.reportKey, start, end }).toString();
      const res = await fetch(`${API_BASE_URL}/reports/export?${q}`, { headers: { 'x-token': user?.token || '' } });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `ออกรายงานไม่สำเร็จ (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${report.reportKey}_${start}_${end}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      Swal.fire('ออกรายงานไม่สำเร็จ', e instanceof Error ? e.message : '', 'error');
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="glass-card w-100 p-4 mb-4">
      <h5 className="text-white mb-1"><i className="fa-solid fa-file-excel text-success"></i> ออกรายงานเป็น Excel</h5>
      <p className="text-white-50 small mb-3">เลือกช่วงวันที่แล้วกดออกรายงาน ค่าเริ่มต้นคือสัปดาห์นี้</p>

      <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
        <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 170 }}
               value={start} onChange={(e) => setStart(e.target.value)} />
        <span className="text-white-50">ถึง</span>
        <input type="date" className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 170 }}
               value={end} onChange={(e) => setEnd(e.target.value)} />
      </div>

      {reports.length ? (
        <div className="table-responsive">
          <table className="table table-sc table-bordered align-middle small mb-0">
            <thead><tr><th className="text-start">แบบฟอร์ม</th><th>รอบส่ง</th><th>reportKey</th><th></th></tr></thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.reportKey}>
                  <td className="text-start text-white">{r.title}</td>
                  <td className="text-white-50">{r.cadence}</td>
                  <td className="text-white-50"><code>{r.reportKey}</code></td>
                  <td>
                    <button className="btn btn-sm btn-success" disabled={busy === r.reportKey}
                            onClick={() => download(r)}>
                      {busy === r.reportKey ? 'กำลังสร้าง...' : 'ออก Excel'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-white-50 small mb-0">ยังไม่มีแบบฟอร์มที่ออกอัตโนมัติได้</p>
      )}

      <div className="alert alert-warning mt-3 mb-0 py-2 small">
        <strong>แบบฟอร์มที่ยังออกไม่ได้</strong> — ที่กรองด้วยป้ายหมวด (บุหรี่ไฟฟ้า · น้ำหนักเกิน ·
        อาวุธปืน · คดีอาญา 5 กลุ่ม) ต้องไปเพิ่มข้อหากลุ่มนั้นและติด <code>reportTags</code>
        ที่เมนู <strong>จัดการข้อหา</strong> ก่อน ตอนนี้ข้อหาในระบบเป็นคดีจราจรทั้งหมดและยังไม่มีตัวไหนติดป้าย
        ออกไปตอนนี้จะได้รายงานที่เป็นศูนย์ทุกช่อง
      </div>
    </div>
  );
};
