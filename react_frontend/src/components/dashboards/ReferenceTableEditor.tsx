import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import Swal from 'sweetalert2';

/**
 * แก้ตารางอ้างอิงของ บก. — ใช้ตัวเดียวกับทั้งสามเมนู
 *
 *   charges         ข้อหา (tb_Charges) — ป้อน dropdown ของฟอร์มจับกุมทุกใบ
 *   seized-items    ประเภทของกลาง (tb_SeizedItemTypes)
 *   report-catalog  รายการรายงาน (tb_ReportCatalog)
 *
 * คอลัมน์ไม่เท่ากันทั้งสามตาราง จึงสร้างฟอร์มจากหัวตารางที่ API ส่งกลับมา แทนที่จะ
 * ฮาร์ดโค้ดสามชุด เพิ่มคอลัมน์ในชีตแล้วหน้านี้รับได้เองโดยไม่ต้องแก้โค้ด
 */

interface Props { kind: 'charges' | 'seized-items' | 'report-catalog' }

export const ReferenceTableEditor: React.FC<Props> = ({ kind }) => {
  const { user } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [keyColumn, setKeyColumn] = useState('');
  const [activeColumn, setActiveColumn] = useState<string | null>(null);
  const [label, setLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [q, setQ] = useState('');

  const load = async () => {
    setLoading(true);
    const res = await api.getReferenceTable(kind, user?.token);
    setLoading(false);
    if (res.status !== 'success') return setErr(res.message || 'โหลดข้อมูลไม่สำเร็จ');
    setErr('');
    const data = res.data || [];
    setRows(data);
    setKeyColumn(res.keyColumn || '');
    setActiveColumn(res.activeColumn ?? null);
    setLabel(res.label || '');
    setColumns(data.length ? Object.keys(data[0]).filter((c) => c !== '_row') : []);
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((r) => columns.some((c) => String(r[c] || '').toLowerCase().includes(needle)));
  }, [rows, q, columns]);

  const isOff = (r: any) => activeColumn && String(r[activeColumn] || '').toUpperCase() === 'FALSE';

  const editRow = async (row: any | null) => {
    const fields = columns.filter((c) => c !== activeColumn);
    const html = fields.map((c) => `
      <label style="display:block;text-align:left;font-size:.78rem;color:#9ca3af;margin-top:.5rem">${c}</label>
      <input id="rf-${c}" class="swal2-input" style="margin:.2rem 0 0;width:100%"
             value="${String((row || {})[c] || '').replace(/"/g, '&quot;')}">`).join('');

    const { value } = await Swal.fire({
      title: row ? `แก้${label}` : `เพิ่ม${label}`,
      html: `<div style="max-height:55vh;overflow:auto">${html}</div>`,
      focusConfirm: false,
      showCancelButton: true,
      confirmButtonText: 'บันทึก',
      cancelButtonText: 'ยกเลิก',
      width: 620,
      preConfirm: () => {
        const out: Record<string, string> = {};
        for (const c of fields) out[c] = (document.getElementById(`rf-${c}`) as HTMLInputElement)?.value.trim() || '';
        if (!out[keyColumn]) {
          Swal.showValidationMessage(`กรุณาระบุ${keyColumn}`);
          return false;
        }
        return out;
      },
    });
    if (!value) return;

    const res = await api.saveReferenceRow(kind, value, row ? row[keyColumn] : null, user?.token);
    if (res.status !== 'success') return Swal.fire('บันทึกไม่สำเร็จ', res.message || '', 'error');
    await load();
    Swal.fire('สำเร็จ', res.message || '', 'success');
  };

  const toggle = async (row: any) => {
    const turningOff = !isOff(row);
    if (turningOff) {
      const c = await Swal.fire({
        title: `ปิดใช้งาน${label}นี้?`,
        html: `<p style="font-size:.9rem">"${row[keyColumn]}" จะหายจาก dropdown ตอนกรอกฟอร์ม<br>
               <span style="color:#9ca3af">รายงานเก่าที่อ้างถึงยังอยู่ครบ และกดเปิดคืนได้ทุกเมื่อ</span></p>`,
        icon: 'warning', showCancelButton: true, confirmButtonText: 'ปิดใช้งาน', cancelButtonText: 'ยกเลิก',
        confirmButtonColor: '#ef4444',
      });
      if (!c.isConfirmed) return;
    }
    const res = await api.setReferenceRowActive(kind, row[keyColumn], !turningOff, user?.token);
    if (res.status !== 'success') return Swal.fire('ทำรายการไม่สำเร็จ', res.message || '', 'error');
    await load();
  };

  if (loading) return <div className="glass-card w-100 p-5 text-center text-white-50">กำลังโหลด...</div>;
  if (err) return <div className="glass-card w-100 p-4"><div className="alert alert-warning m-0">{err}</div></div>;

  return (
    <div className="glass-card w-100 p-4">
      <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
        <input className="form-control bg-dark text-white border-secondary" style={{ maxWidth: 320 }}
               placeholder="ค้นหา" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn btn-sm btn-success" onClick={() => editRow(null)}>
          <i className="fa-solid fa-plus"></i> เพิ่ม{label}
        </button>
        <button className="btn btn-sm btn-outline-info" onClick={load}><i className="fa-solid fa-rotate"></i></button>
        <span className="text-white-50 small ms-auto">แสดง {shown.length} จาก {rows.length} รายการ</span>
      </div>

      {!activeColumn && (
        <p className="text-white-50 small">
          ตารางนี้ไม่มีคอลัมน์เปิด/ปิดใช้งาน จึงแก้และเพิ่มได้ แต่ปิดใช้งานรายแถวไม่ได้
        </p>
      )}

      <div className="table-responsive" style={{ maxHeight: '58vh' }}>
        <table className="table table-sc table-bordered align-middle small">
          <thead><tr>{columns.map((c) => <th key={c} className="text-nowrap">{c}</th>)}<th></th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r._row} style={isOff(r) ? { opacity: 0.45 } : undefined}>
                {columns.map((c) => (
                  <td key={c} className={c === keyColumn ? 'text-white fw-bold' : 'text-white-50'}>{r[c] || '-'}</td>
                ))}
                <td className="text-nowrap">
                  <button className="btn btn-sm btn-outline-light me-1" onClick={() => editRow(r)}>แก้ไข</button>
                  {activeColumn && (
                    <button className={`btn btn-sm ${isOff(r) ? 'btn-outline-success' : 'btn-outline-danger'}`}
                            onClick={() => toggle(r)}>
                      {isOff(r) ? 'เปิดใช้งาน' : 'ปิดใช้งาน'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!shown.length && <tr><td colSpan={columns.length + 1} className="text-center text-white-50 py-4">ไม่พบรายการ</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};
