import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { FormShell } from './FormShell';
import { getNowDateTimeLocal, loadingModal } from '../../utils/formHelpers';
import Swal from 'sweetalert2';

interface AASuspect { name: string; idCard: string; nat: string; age: string; address: string; phone: string }

export const ToolsForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const [view, setView] = useState<'dashboard' | 'autoArrest'>('dashboard');
  const [aa, setAa] = useState<Record<string, string>>({
    recordDate: getNowDateTimeLocal(), arrestDate: getNowDateTimeLocal(), offense: '', arrestLocation: '',
    detentionLocation: '', circumstances: '', briefCircumstances: '',
    respOfficer: user?.fullName || '', respPhone: '', notifyOfficer: user?.fullName || '', notifyPhone: '',
  });
  const set = (k: string, v: string) => setAa((p) => ({ ...p, [k]: v }));
  const [suspects, setSuspects] = useState<AASuspect[]>([{ name: '', idCard: '', nat: '', age: '', address: '', phone: '' }]);

  const combinedText = suspects
    .map((s, i) => `${i + 1}. ${s.name || '...'} อายุ ${s.age || '...'} ปี เลขบัตรประจำตัวประชาชน ${s.idCard || '...'} สัญชาติ${s.nat || '...'} ที่อยู่ ${s.address || '...'} เบอร์โทร ${s.phone || '...'}`)
    .join('\n');

  const submitAuto = async () => {
    loadingModal('กำลังเชื่อมต่อฐานข้อมูลและสร้างเอกสาร...');
    const payload = { ...aa, allSuspectsText: combinedText };
    const res = await api.submitReport('auto-arrest', payload, user?.token, { suspectArray: suspects });
    if (res.status === 'success') {
      const links: { url: string; name: string }[] = res.links || [];
      const linksHtml = links.length
        ? `<div class="text-start mt-3">${links.map((l) => `<a href="${l.url}" target="_blank" class="btn btn-outline-success btn-sm w-100 mb-2"><i class="fa-solid fa-download"></i> โหลด: ${l.name}</a>`).join('')}</div>`
        : '<p class="small text-white-50 mt-2">(โหมดสาธิต - ยังไม่ได้เชื่อมระบบสร้างเอกสารจริง)</p>';
      await Swal.fire({ icon: 'success', title: 'สร้างเอกสารสำเร็จ!', html: `ระบบได้บันทึกไฟล์ลงใน Google Drive เรียบร้อยแล้ว${linksHtml}`, confirmButtonColor: '#00f2ff' });
      setView('dashboard');
    } else {
      Swal.fire('เกิดข้อผิดพลาด', res.message || 'สร้างเอกสารไม่สำเร็จ', 'error');
    }
  };

  if (view === 'autoArrest') {
    return (
      <FormShell title="ออกเอกสารจับกุมอัตโนมัติ" onBack={() => setView('dashboard')} backLabel="กลับ" maxWidth={900}>
        <div className="glass-card w-100">
          <h5 className="text-info mt-2"><i className="fa-solid fa-clock"></i> ๑. ข้อมูลวันเวลา</h5>
          <div className="row g-3 mb-4">
            <div className="col-12 col-md-6"><label className="form-label text-light">วันที่เวลาที่บันทึก</label><input type="datetime-local" className="form-control" value={aa.recordDate} onChange={(e) => set('recordDate', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">วันที่เวลาที่จับกุม</label><input type="datetime-local" className="form-control" value={aa.arrestDate} onChange={(e) => set('arrestDate', e.target.value)} /></div>
          </div>

          <h5 className="text-info mt-4"><i className="fa-solid fa-users"></i> ๒. ข้อมูลผู้ต้องหาทั้งหมด</h5>
          <div className="mb-4"><textarea rows={4} className="form-control bg-dark text-white-50" readOnly value={combinedText} placeholder="ระบบจะดึงข้อมูลจากข้อ ๓ มาเรียงให้อัตโนมัติ" /></div>

          <div className="d-flex justify-content-between align-items-center mt-4 mb-2 border-bottom border-secondary pb-2">
            <h5 className="mb-0 text-info"><i className="fa-solid fa-user-tag"></i> ๓. ข้อมูลผู้ต้องหารายบุคคล (ม.22,23)</h5>
            <button type="button" className="btn btn-sm btn-outline-warning" onClick={() => setSuspects((p) => [...p, { name: '', idCard: '', nat: '', age: '', address: '', phone: '' }])}>+ เพิ่ม 1 ราย</button>
          </div>
          <div className="mb-4">
            {suspects.map((s, i) => {
              const su = (k: keyof AASuspect, v: string) => setSuspects((p) => p.map((x, idx) => (idx === i ? { ...x, [k]: v } : x)));
              return (
                <div className="p-3 mb-3 rounded border border-info position-relative" style={{ background: 'rgba(0, 242, 255, 0.05)' }} key={i}>
                  <span className="position-absolute top-0 end-0 badge bg-info mt-2 me-2">คนที่ #{i + 1}</span>
                  <div className="row g-2 mt-1">
                    <div className="col-12 col-md-6"><input type="text" placeholder="นาย/นาง/นางสาว ชื่อ-สกุล" className="form-control" value={s.name} onChange={(e) => su('name', e.target.value)} /></div>
                    <div className="col-12 col-md-6"><input type="text" placeholder="เลขบัตรประชาชน" className="form-control" value={s.idCard} onChange={(e) => su('idCard', e.target.value)} /></div>
                    <div className="col-12 col-md-6"><input type="text" placeholder="สัญชาติ" className="form-control" value={s.nat} onChange={(e) => su('nat', e.target.value)} /></div>
                    <div className="col-12 col-md-6"><input type="number" placeholder="อายุ" className="form-control" value={s.age} onChange={(e) => su('age', e.target.value)} /></div>
                    <div className="col-12"><input type="text" placeholder="ที่อยู่" className="form-control" value={s.address} onChange={(e) => su('address', e.target.value)} /></div>
                    <div className="col-12"><input type="tel" placeholder="เบอร์โทร" className="form-control" value={s.phone} onChange={(e) => su('phone', e.target.value)} /></div>
                    {suspects.length > 1 && <div className="col-12 text-end"><button type="button" className="btn btn-sm btn-outline-danger" onClick={() => setSuspects((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i> ลบ</button></div>}
                  </div>
                </div>
              );
            })}
          </div>

          <h5 className="text-info mt-4"><i className="fa-solid fa-gavel"></i> ๔. ข้อมูลคดี</h5>
          <div className="row g-3 mb-4">
            <div className="col-12"><label className="form-label text-light">ฐานความผิด</label><textarea rows={2} className="form-control" value={aa.offense} onChange={(e) => set('offense', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">สถานที่จับกุม</label><textarea rows={2} className="form-control" value={aa.arrestLocation} onChange={(e) => set('arrestLocation', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">สถานที่ควบคุม</label><textarea rows={2} className="form-control" value={aa.detentionLocation} onChange={(e) => set('detentionLocation', e.target.value)} /></div>
            <div className="col-12"><label className="form-label text-light">พฤติการณ์ (สำหรับบันทึกจับกุม)</label><textarea rows={3} className="form-control" value={aa.circumstances} onChange={(e) => set('circumstances', e.target.value)} /></div>
            <div className="col-12"><label className="form-label text-warning">พฤติการณ์โดยย่อ (สำหรับ ม.22,23)</label><textarea rows={2} className="form-control border-warning" style={{ background: 'rgba(255,193,7,0.05)' }} value={aa.briefCircumstances} onChange={(e) => set('briefCircumstances', e.target.value)} /></div>
          </div>

          <h5 className="text-info mt-4"><i className="fa-solid fa-user-shield"></i> ๕. เจ้าหน้าที่</h5>
          <div className="row g-3 mb-4">
            <div className="col-12 col-md-6"><label className="form-label text-light">ชื่อเจ้าหน้าที่ผู้รับผิดชอบ</label><input type="text" className="form-control" value={aa.respOfficer} onChange={(e) => set('respOfficer', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">เบอร์โทรผู้รับผิดชอบ</label><input type="tel" className="form-control" value={aa.respPhone} onChange={(e) => set('respPhone', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">ชื่อเจ้าหน้าที่ผู้แจ้ง</label><input type="text" className="form-control" value={aa.notifyOfficer} onChange={(e) => set('notifyOfficer', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label text-light">เบอร์โทรผู้แจ้ง</label><input type="tel" className="form-control" value={aa.notifyPhone} onChange={(e) => set('notifyPhone', e.target.value)} /></div>
          </div>

          <button type="button" className="btn-primary-custom py-3 mt-2" onClick={submitAuto}><i className="fa-solid fa-file-export"></i> บันทึกข้อมูลและออกเอกสารทันที</button>
        </div>
      </FormShell>
    );
  }

  return (
    <FormShell title="เครื่องมือการทำงาน" onBack={onBack} maxWidth={900}>
      <div className="glass-card w-100 mb-4">
        <div className="row g-3 mb-4">
          <div className="col-12 col-md-4">
            <button className="btn-primary-custom h-100 py-4 w-100" onClick={() => setView('autoArrest')}>
              <i className="fa-solid fa-file-invoice text-warning fa-2x mb-2"></i><br />ออกเอกสารจับกุม<br /><small className="text-white-50">(อัตโนมัติแบบฟอร์ม)</small>
            </button>
          </div>
          <div className="col-12 col-md-4">
            <a href="https://sites.google.com/view/case-study-hwpd/Home" target="_blank" rel="noreferrer" className="btn btn-outline-info w-100 h-100 py-4 d-flex flex-column align-items-center justify-content-center" style={{ borderRadius: 15 }}>
              <i className="fa-solid fa-book fa-2x mb-2"></i><span>คู่มือการทำงาน</span>
            </a>
          </div>
          <div className="col-12 col-md-4">
            <a href="https://secretive-sundae-24e.notion.site/5-2ddd6231c7bb80afb1f0eb3a129f3bc3?source=copy_link" target="_blank" rel="noreferrer" className="btn btn-outline-success w-100 h-100 py-4 d-flex flex-column align-items-center justify-content-center" style={{ borderRadius: 15 }}>
              <i className="fa-brands fa-google-drive fa-2x mb-2"></i><span>คลังฟอร์มเอกสาร</span>
            </a>
          </div>
        </div>

        <h5 className="text-warning border-bottom border-secondary pb-2 mt-5"><i className="fa-solid fa-bullhorn"></i> ประกาศข่าวสารจากผู้บังคับบัญชา</h5>
        <div className="mt-3" style={{ maxHeight: 300, overflowY: 'auto' }}>
          <div className="alert text-light border border-info mb-2" style={{ background: 'rgba(0, 242, 255, 0.1)' }}>
            <small className="text-info"><i className="fa-regular fa-clock"></i> 27 พ.ค. 2569</small><br />
            <span className="badge bg-warning text-dark mb-1">ฝอ. กก.5</span><br />
            <strong>ทดสอบระบบข่าวสาร:</strong> เร็วๆ นี้จะมีการอัปเดตระบบส่งประกาศข่าวสารจากหน้า Commander Dashboard มาแสดงที่นี่ครับ
          </div>
        </div>
      </div>
    </FormShell>
  );
};
