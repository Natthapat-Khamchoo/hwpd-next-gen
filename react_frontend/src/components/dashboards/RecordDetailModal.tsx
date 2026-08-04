import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import type { RecordDetail } from '../../types';
import Swal from 'sweetalert2';

/**
 * ตรวจรายละเอียดรายงานก่อนอนุมัติ (requirement ข้อ 9)
 * และแก้ไขรายการของตัวเองที่ยังรออนุมัติ (requirement ข้อ 10)
 *
 * ของเดิมหน้าแอดมินกดอนุมัติจากตารางได้เลย เห็นแค่ประเภทรายงานกับชื่อผู้ส่ง
 * ซึ่งแปลว่าการอนุมัติเป็นการกดผ่านโดยไม่ได้ตรวจอะไรจริง ๆ
 *
 * **ปุ่มยืนยันอนุมัติถูกปิดไว้จนกว่าจะโหลดรายละเอียดเสร็จ** ถ้าเปิดให้กดได้ระหว่าง
 * ที่ยังโหลดอยู่ ผลลัพธ์จะเหมือนของเดิมทุกประการ คือกดอนุมัติโดยไม่เห็นเนื้อรายงาน
 */

interface Props {
  sheetName: string;
  recordId: string;
  /** ป้ายประเภทรายงานจากตารางคิว ใช้เป็นหัวเรื่องระหว่างรอโหลด */
  formType?: string;
  mode: 'approve' | 'view';
  onClose: () => void;
  /** เรียกเมื่อแอดมินกดยืนยันอนุมัติในกล่องนี้ */
  onApprove?: () => void;
  /** เรียกหลังแก้ไขสำเร็จ ให้หน้าแม่โหลดรายการใหม่ */
  onUpdated?: () => void;
}

export const RecordDetailModal: React.FC<Props> = ({
  sheetName,
  recordId,
  formType,
  mode,
  onClose,
  onApprove,
  onUpdated,
}) => {
  const { user } = useAuth();
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    api.getRecordDetail(sheetName, recordId, user?.token).then((res) => {
      if (!alive) return;
      if (res.status === 'success' && res.data) setDetail(res.data);
      else setError(res.message || 'ดึงรายละเอียดไม่สำเร็จ');
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetName, recordId]);

  const startEditing = () => {
    if (!detail) return;
    const seed: Record<string, string> = {};
    detail.fields.forEach((f) => {
      if (detail.editableFields.includes(f.label)) seed[f.label] = f.value;
    });
    setEdits(seed);
    setEditing(true);
  };

  const save = async () => {
    if (!detail) return;
    // ส่งเฉพาะช่องที่ค่าเปลี่ยนจริง ฝั่ง API ก็กรองซ้ำอีกชั้น แต่การส่งทั้งชุดมาแล้ว
    // ให้ปลายทางกรองทำให้ audit log อ่านยากถ้าวันหนึ่งมีบั๊กที่ฝั่งใดฝั่งหนึ่ง
    const original = new Map(detail.fields.map((f) => [f.label, f.value]));
    const changed: Record<string, string> = {};
    Object.entries(edits).forEach(([key, value]) => {
      if ((original.get(key) ?? '') !== value) changed[key] = value;
    });

    if (!Object.keys(changed).length) {
      Swal.fire('ไม่มีการเปลี่ยนแปลง', 'ยังไม่ได้แก้ไขช่องไหนเลย', 'info');
      return;
    }

    setSaving(true);
    const res = await api.updateRecord(sheetName, recordId, changed, user?.token);
    setSaving(false);
    if (res.status !== 'success') {
      Swal.fire('แก้ไขไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    await Swal.fire('บันทึกแล้ว', res.message || '', 'success');
    onUpdated?.();
    onClose();
  };

  const confirmApprove = async () => {
    const r = await Swal.fire({
      title: 'ยืนยันการอนุมัติ',
      html: `ตรวจรายละเอียดของ <b>${recordId}</b> เรียบร้อยแล้วใช่หรือไม่?<br>
             <span class="small text-muted">เมื่ออนุมัติแล้วยอดจะถูกนับเข้ารายงานของหน่วยทันที</span>`,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'อนุมัติ',
      cancelButtonText: 'กลับไปตรวจต่อ',
      confirmButtonColor: '#10b981',
    });
    if (!r.isConfirmed) return;
    onApprove?.();
    onClose();
  };

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-start justify-content-center"
      style={{ background: 'rgba(0,0,0,.75)', zIndex: 2000, overflowY: 'auto', padding: '3vh 1rem' }}
    >
      <div className="glass-card p-4" style={{ maxWidth: 820, width: '100%' }}>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <div>
            <h5 className="text-white m-0">
              <i className="fa-solid fa-file-magnifying-glass text-info"></i>{' '}
              {mode === 'approve' ? 'ตรวจรายละเอียดก่อนอนุมัติ' : 'รายละเอียดรายงาน'}
            </h5>
            <small className="text-white-50">{formType || detail?.table} · {recordId}</small>
          </div>
          <button className="btn btn-sm btn-outline-light" onClick={onClose}>ปิด</button>
        </div>

        {error && <div className="alert alert-danger py-2">{error}</div>}

        {!detail && !error && (
          <div className="text-center py-5 text-white-50">
            <span className="spinner-border spinner-border-sm text-info me-2"></span>
            กำลังโหลดรายละเอียด...
          </div>
        )}

        {detail && (
          <>
            <div className="row g-2 mb-3 small">
              {([
                ['ผู้ส่ง', detail.actionBy],
                ['หน่วย', detail.unit || detail.station],
                ['วันที่ข้อมูล', detail.date],
                ['เวลาที่ส่ง', detail.timestamp],
              ] as const).map(([label, value]) => (
                <div className="col-6 col-md-3" key={label}>
                  <div className="p-2 rounded" style={{ background: 'rgba(255,255,255,0.04)' }}>
                    <div className="text-white-50" style={{ fontSize: '0.7rem' }}>{label}</div>
                    <div className="text-white">{value || '-'}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="table-responsive" style={{ maxHeight: '46vh', overflowY: 'auto' }}>
              <table className="table table-sm table-hq align-middle mb-0">
                <tbody>
                  {detail.fields.map((f) => {
                    const canEditThis = editing && detail.editableFields.includes(f.label);
                    return (
                      <tr key={f.label}>
                        <td className="small" style={{ width: '38%', opacity: 0.65 }}>{f.label}</td>
                        <td>
                          {canEditThis ? (
                            <input
                              className="form-control form-control-sm"
                              value={edits[f.label] ?? f.value}
                              onChange={(e) => setEdits((p) => ({ ...p, [f.label]: e.target.value }))}
                            />
                          ) : (
                            <span style={{ whiteSpace: 'pre-wrap' }}>{f.value}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-3">
              <div className="small text-white-50 mb-2">
                <i className="fa-solid fa-paperclip"></i> ไฟล์แนบ
              </div>
              {detail.attachments.length ? (
                <div className="d-flex flex-wrap gap-2">
                  {detail.attachments.map((url, i) => (
                    <a key={url} className="btn btn-sm btn-outline-info" href={url} target="_blank" rel="noreferrer">
                      <i className="fa-solid fa-folder-open"></i> เปิดดูไฟล์แนบ {detail.attachments.length > 1 ? i + 1 : ''}
                    </a>
                  ))}
                </div>
              ) : (
                <div className="small text-warning">
                  <i className="fa-solid fa-triangle-exclamation"></i> รายการนี้ไม่มีไฟล์แนบ
                </div>
              )}
            </div>

            <div className="d-flex flex-wrap gap-2 mt-4">
              {mode === 'approve' && (
                <button className="btn btn-success fw-bold flex-grow-1" onClick={confirmApprove}>
                  <i className="fa-solid fa-check"></i> ตรวจแล้ว ยืนยันอนุมัติ
                </button>
              )}
              {detail.canEdit && !editing && (
                <button className="btn btn-outline-warning flex-grow-1" onClick={startEditing}>
                  <i className="fa-solid fa-pen"></i> แก้ไขรายการนี้
                </button>
              )}
              {editing && (
                <>
                  <button className="btn btn-warning fw-bold flex-grow-1" onClick={save} disabled={saving}>
                    <i className="fa-solid fa-floppy-disk"></i> {saving ? 'กำลังบันทึก...' : 'บันทึกการแก้ไข'}
                  </button>
                  <button className="btn btn-outline-light" onClick={() => setEditing(false)} disabled={saving}>
                    ยกเลิกการแก้ไข
                  </button>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
