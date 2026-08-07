import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { useFormDraft } from '../../hooks/useFormDraft';
import { FormShell } from './FormShell';
import { DraftNotice } from './DraftNotice';
import { LocationPickerButton } from '../common/LocationPickerButton';
import { ChargeSelect, ChargeGroupToggle } from './ChargeSelect';
import { chargeList, missingArrestFields } from './arrestValidation';
import { ThaiDateInput } from './ThaiDateInput';
import {
  getNowDateTimeLocal,
  getFrontendStationData,
  formatPreviewDate,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

interface Suspect { name: string; idCard: string; nat: string; age: string; address: string }
interface Seized { name: string; qty: string; note: string }

const CATEGORIES = ['ยาเสพติด', 'พ.ร.บ.จราจรทางบก', 'พ.ร.บ.รถยนต์ (ป้ายปลอม/สวมทะเบียน)', 'อาวุธปืน/เครื่องกระสุน', 'บุคคลต่างด้าวหลบหนีเข้าเมือง', 'จับตามหมายจับ (คดีค้างเก่า)', 'เมาแล้วขับ', 'สินค้าหนีภาษี/ศุลกากร', 'พ.ร.บ.ป่าไม้/สัตว์ป่า', 'อื่นๆ'];

export const ArrestForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { users, charges, chargeGroups } = useStationData({ charges: true });
  // requirement ข้อ 14 — เปิดจัดกลุ่มไว้เป็นค่าเริ่มต้น เพราะรายการข้อหายาวจนหายาก
  const [groupCharges, setGroupCharges] = useState(true);

  const blank: Record<string, string> = {
    reportDateTime: getNowDateTimeLocal(),
    category: '', arrestBy: 'จับเอง', arrestType: 'จับกุมซึ่งหน้า', warrantType: 'ไม่ใช่หมายจับ', warrantScope: 'ไม่ใช่หมายจับ',
    actionDateTime: getNowDateTimeLocal(), caseMethod: '', caseNumber: '', suspectCount: '1',
    location: '', lat: '', lng: '', items: '', ecigType: '', relatedUrl: '', damageValue: '', turnoverValue: '',
    circumstances: '', forwarding: '',
  };
  const [f, setF, draft] = useFormDraft('arrest', blank, user?.username);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  // ฟอร์มจับกุมเป็นฟอร์มที่ยาวที่สุดในระบบและมีตารางย่อยสี่ชุด ถ้าเก็บร่างแค่ฟิลด์หลัก
  // แล้วรายชื่อชุดจับกุมกับผู้ต้องหาหาย จะแย่กว่าไม่เก็บเลย เพราะคนจะเชื่อว่าครบแล้วส่งไป
  const BLANK_TEAM: string[] = [''];
  const BLANK_CHARGES = [{ value: '', other: '' }];
  const BLANK_SUSPECTS: Suspect[] = [{ name: '', idCard: '', nat: '', age: '', address: '' }];
  const [team, setTeam, teamDraft] = useFormDraft('arrest.team', BLANK_TEAM, user?.username);
  const [chargeRows, setChargeRows, chargeDraft] = useFormDraft('arrest.charges', BLANK_CHARGES, user?.username);
  const [suspects, setSuspects, suspectDraft] = useFormDraft('arrest.suspects', BLANK_SUSPECTS, user?.username);
  const [seized, setSeized, seizedDraft] = useFormDraft('arrest.seized', [] as Seized[], user?.username);
  const [manualItems, setManualItems] = useState(false);
  const [files, setFiles] = useState<FileList | null>(null);

  const clearDraft = () => {
    draft.clear();
    teamDraft.clear();
    chargeDraft.clear();
    suspectDraft.clear();
    seizedDraft.clear();
  };

  const resetForm = () => {
    clearDraft();
    setF({ ...blank, reportDateTime: getNowDateTimeLocal(), actionDateTime: getNowDateTimeLocal() });
    setTeam([...BLANK_TEAM]);
    setChargeRows(BLANK_CHARGES.map((r) => ({ ...r })));
    setSuspects(BLANK_SUSPECTS.map((s) => ({ ...s })));
    setSeized([]);
  };

  // compose seized -> items text unless user edited manually
  const composeItems = (rows: Seized[]) => {
    if (manualItems) return;
    const lines = rows.filter((r) => r.name).map((r, i) => {
      let line = `${i + 1}. ${r.name}`;
      if (r.qty) line += ` จำนวน ${r.qty}`;
      if (r.note) line += ` - ${r.note}`;
      return line;
    });
    if (lines.length) set('items', lines.join('\n'));
  };

  const missingFields = () => missingArrestFields({ team, chargeRows, suspects, f });

  const warnMissing = (missing: string[]) =>
    Swal.fire({
      icon: 'warning',
      title: 'ข้อมูลไม่ครบ',
      html: `<div class="text-start">ยังขาดข้อมูลต่อไปนี้<ul class="mt-2 mb-0">${missing.map((m) => `<li>${m}</li>`).join('')}</ul></div>`,
      confirmButtonColor: '#dc3545',
    });

  const submit = async () => {
    const missing = missingFields();
    if (missing.length) return warnMissing(missing);

    const teamArr = team.filter(Boolean);
    const chargeArr = chargeList(chargeRows);

    const st = getFrontendStationData(user?.station);
    const actionDateStr = formatPreviewDate(f.actionDateTime.split('T')[0]);
    const actionTimeStr = (f.actionDateTime.split('T')[1] || '').replace(':', '.');
    const teamText = teamArr.join(', ');
    const chargeText = chargeArr.map((c, i) => `${i + 1}. ${c}`).join('\n');
    const suspectLineText = suspects
      .map((s) => `ชื่อ ${s.name}\nเลขบัตรประจำตัวประชาชน/พาสปอร์ต: ${s.idCard}\nสัญชาติ: ${s.nat}\nอายุ: ${s.age} ปี\nที่อยู่: ${s.address}\n`)
      .join('\n');
    const gg = (v: string, label: string) => (v ? `\n${label}: ${v}` : '');
    const warrantScopeLine = f.warrantScope && f.warrantScope !== 'ไม่ใช่หมายจับ' ? `\nขอบเขตหมาย: ${f.warrantScope}` : '';

    const previewText =
      `เรียน ผู้บังคับบัญชา\nหน่วยงาน บก.ทล.\nกก.: ${String(user?.station).trim().substring(0, 1)}\n${st.f}\n` +
      `หัวข้อ: จับกุม ${f.category}\nจับโดย: ${f.arrestBy}\nประเภทการจับกุม: ${f.arrestType}${warrantScopeLine}` +
      `${gg(f.caseMethod, 'การปฏิบัติ')}${gg(f.caseNumber, 'เลขคดี')}\nวันที่ : ${actionDateStr}\nเวลา: ${actionTimeStr} น.\n` +
      `เจ้าหน้าที่ชุดจับกุม : เจ้าหน้าที่ ${st.f}\nประกอบด้วย ${teamText}\nข้อมูลผู้ต้องหา:\n` +
      `จำนวน ผู้ต้องหา: ${f.suspectCount} คน\n${suspectLineText.trim()}\n\nข้อหา: \n${chargeText}\n` +
      `สถานที่จับกุม/เกิดเหตุ: ${f.location}\nละติจูด : ${f.lat}\nลองจิจูด : ${f.lng}\nของกลาง: ${f.items}` +
      `${gg(f.ecigType, 'ประเภทคดีบุหรี่ไฟฟ้า')}${gg(f.relatedUrl, 'เว็บไซต์/URL')}${gg(f.damageValue, 'มูลค่าความเสียหาย')}${gg(f.turnoverValue, 'วงเงินหมุนเวียน')}\n` +
      `พฤติการณ์ : ${f.circumstances}\nการดำเนินการส่งต่อ : ${f.forwarding}\nไฟล์แนบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;

    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึกและส่งแจ้งเตือน...');
    const payload = { ...f, unitId: user?.unit, stationId: user?.station, actionBy: user?.username };
    const attachments = await filesToBase64(files);
    const res = await api.submitReport('arrest', payload, user?.token, {
      files: attachments, teamArray: teamArr, suspectArray: suspects, chargeArray: chargeArr, seizedItems: seized,
    });
    if (res.status === 'success') {
      clearDraft();
      await showLineCopyResult(res.message || 'บันทึกรายงานจับกุมสำเร็จ', res.lineText || previewText, copied ? previewText : undefined);
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'บันทึกไม่สำเร็จ', 'error');
    }
  };

  const generateAutoDocs = async () => {
    const missing = missingFields();
    if (missing.length) return warnMissing(missing);
    loadingModal('กำลังดึงแม่แบบและสร้างเอกสารจับกุม...');
    const combinedSuspectsText = suspects
      .map((s, i) => `${i + 1}. ${s.name || '...'} อายุ ${s.age || '...'} ปี เลขบัตรประจำตัวประชาชน ${s.idCard || '...'} สัญชาติ ${s.nat || '...'} ที่อยู่ ${s.address || '...'}`)
      .join('\n');
    const payload = {
      recordDate: f.reportDateTime,
      arrestDate: f.actionDateTime,
      offense: chargeRows.map((c) => (c.value === '__OTHER__' ? c.other : c.value)).filter(Boolean).join(', '),
      arrestLocation: f.location,
      detentionLocation: f.location,
      circumstances: f.circumstances,
      briefCircumstances: f.circumstances,
      allSuspectsText: combinedSuspectsText,
      respOfficer: user?.fullName || '',
      respPhone: '',
      forwarding: f.forwarding,
    };
    const res = await api.submitReport('auto-arrest', payload, user?.token, { suspectArray: suspects });
    if (res.status !== 'success') {
      Swal.fire('เกิดข้อผิดพลาด', res.message || 'สร้างเอกสารไม่สำเร็จ', 'error');
      return;
    }

    /*
     * backend สร้างไฟล์ .docx ในเครื่องแล้วส่งไบต์กลับมาเลย (`files`) ไม่ต้องแวะ Drive
     * เครื่องที่ยังไม่ได้ลง python-docx จะถอยไปใช้ Google Docs แล้วส่ง `links` มาแทน
     * จึงรองรับทั้งสองแบบ ไม่งั้นการ deploy ที่ไลบรารียังไม่ครบจะกลายเป็นปุ่มที่กดแล้วเงียบ
     */
    const files: { name: string; filename: string; mime: string; data: string }[] = res.files || [];
    const links: { url: string; name: string }[] = res.links || [];

    if (files.length) {
      files.forEach((file) => {
        const bytes = Uint8Array.from(atob(file.data), (ch) => ch.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: file.mime }));
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = file.filename;
        anchor.click();
        URL.revokeObjectURL(url);
      });
    }

    const listHtml = files.length
      ? `<div class="text-start mt-3">${files.map((f) => `<div class="small text-success"><i class="fa-solid fa-check"></i> ${f.filename}</div>`).join('')}</div>`
      : links.length
        ? `<div class="text-start mt-3">${links.map((l) => `<a href="${l.url}" target="_blank" class="btn btn-outline-success btn-sm w-100 mb-2"><i class="fa-solid fa-download"></i> โหลด: ${l.name}</a>`).join('')}</div>`
        : '<p class="small text-white-50 mt-2">(ยังไม่ได้ตั้งค่าแม่แบบเอกสาร ระบบเตรียมข้อมูลไว้พร้อมแล้ว)</p>';

    const warnHtml = res.warning
      ? `<p class="small text-warning mt-2"><i class="fa-solid fa-triangle-exclamation"></i> ${res.warning}</p>`
      : '';

    await Swal.fire({
      icon: 'success',
      title: files.length ? 'ดาวน์โหลดเอกสารแล้ว' : 'สร้างเอกสารจับกุมสำเร็จ!',
      html: `${files.length ? 'ไฟล์ถูกบันทึกลงเครื่องแล้ว' : 'ระบบได้สร้างไฟล์บันทึกจับกุมและเอกสาร ม.22-23 เรียบร้อยแล้ว'}${listHtml}${warnHtml}`,
      confirmButtonColor: '#00f2ff',
    });
  };

  return (
    <FormShell title="รายงานการจับกุม" onBack={onBack} maxWidth={900}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #dc3545' }}>
        {draft.restored && <DraftNotice onClear={resetForm} />}
        <div className="row g-3">
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label>
            <div className="d-flex gap-2"><ThaiDateInput type="datetime-local" value={f.reportDateTime} onChange={(v) => set('reportDateTime', v)} /><button type="button" className="btn btn-outline-danger" onClick={() => set('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div>
          </div>
          <div className="col-12 col-md-6"><label className="form-label small text-white-50">หัวข้อการจับกุม</label>
            <select className="form-select border-danger" value={f.category} onChange={(e) => set('category', e.target.value)}><option value="">-- เลือกหัวข้อ --</option>{CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}</select>
          </div>

          <div className="col-12 col-md-3"><label className="form-label small text-white-50">จับโดย</label><select className="form-select" value={f.arrestBy} onChange={(e) => set('arrestBy', e.target.value)}><option value="จับเอง">จับเอง</option><option value="ร่วมจับ">ร่วมจับ</option></select></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">ประเภทการจับ</label><select className="form-select" value={f.arrestType} onChange={(e) => set('arrestType', e.target.value)}><option value="จับกุมซึ่งหน้า">จับกุมซึ่งหน้า</option><option value="จับตามหมาย">จับตามหมาย</option><option value="จับหมาย Bigdata">จับหมาย Bigdata</option><option value="จับหมาย Bodyworn">จับหมาย Bodyworn</option></select></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">ประเภทหมายจับ</label><select className="form-select border-warning" value={f.warrantType} onChange={(e) => set('warrantType', e.target.value)}><option value="ไม่ใช่หมายจับ">ไม่ใช่หมายจับ</option><option value="หมายศาล">หมายศาล</option><option value="หมายทั่วไป">หมายทั่วไป</option></select></div>
          <div className="col-12 col-md-3"><label className="form-label small text-white-50">ขอบเขตหมาย (กรณีจับตามหมาย)</label><select className="form-select border-warning" value={f.warrantScope} onChange={(e) => set('warrantScope', e.target.value)}><option value="ไม่ใช่หมายจับ">ไม่ใช่หมายจับ</option><option value="หมายใน (บช.ก.)">หมายใน (บช.ก.)</option><option value="หมายนอก">หมายนอก</option></select></div>

          <div className="col-12 col-md-3"><label className="form-label small text-white-50">เวลาเกิดเหตุ</label><ThaiDateInput type="datetime-local" value={f.actionDateTime} onChange={(v) => set('actionDateTime', v)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">การตรวจค้น/แจ้งข้อกล่าวหา (ถ้ามี)</label><select className="form-select" value={f.caseMethod} onChange={(e) => set('caseMethod', e.target.value)}><option value="">— ไม่มี —</option><option value="ตรวจค้น">ตรวจค้น</option><option value="แจ้งข้อกล่าวหา">แจ้งข้อกล่าวหา</option></select></div>
          <div className="col-12 col-md-5"><label className="form-label small text-white-50">เลขคดี (ถ้ามี)</label><input type="text" className="form-control" placeholder="เช่น 123/2569 (เว้นว่างได้)" value={f.caseNumber} onChange={(e) => set('caseNumber', e.target.value)} /></div>

          {/* Arrest team */}
          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12" style={{ background: 'rgba(255,255,255,0.05)', padding: 15, borderRadius: 10 }}>
            <div className="d-flex justify-content-between mb-2"><label className="small text-info">ชุดจับกุม</label><button type="button" className="btn btn-sm btn-info" onClick={() => setTeam((p) => [...p, ''])}><i className="fa-solid fa-plus"></i> เพิ่มนายตำรวจ</button></div>
            {team.map((t, i) => (
              <div className="row g-2 mb-2" key={i}>
                <div className="col-10"><select className="form-select border-info" value={t} onChange={(e) => setTeam((p) => p.map((x, idx) => (idx === i ? e.target.value : x)))}><option value="">-- เลือกรายชื่อ --</option>{users.map((u) => <option key={u} value={u}>{u}</option>)}</select></div>
                <div className="col-2 text-end"><button type="button" className="btn btn-sm btn-outline-danger w-100" onClick={() => setTeam((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i></button></div>
              </div>
            ))}
          </div>

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">จำนวนผู้ต้องหา (คน)</label><input type="number" className="form-control text-center" min="1" value={f.suspectCount} onChange={(e) => set('suspectCount', e.target.value)} /></div>

          {/* Suspects */}
          <div className="col-12" style={{ background: 'rgba(220, 53, 69, 0.1)', padding: 15, borderRadius: 10, border: '1px solid rgba(220, 53, 69, 0.3)' }}>
            <div className="d-flex justify-content-between mb-3"><label className="small text-danger fw-bold"><i className="fa-solid fa-users"></i> ข้อมูลผู้ต้องหา</label><button type="button" className="btn btn-sm btn-danger" onClick={() => setSuspects((p) => [...p, { name: '', idCard: '', nat: '', age: '', address: '' }])}><i className="fa-solid fa-user-plus"></i> เพิ่มผู้ต้องหา</button></div>
            {suspects.map((s, i) => {
              const su = (k: keyof Suspect, v: string) => setSuspects((p) => p.map((x, idx) => (idx === i ? { ...x, [k]: v } : x)));
              return (
                <div className="bg-dark p-3 rounded mb-3 border border-secondary" key={i}>
                  <div className="d-flex justify-content-between mb-2"><span className="text-danger small">ผู้ต้องหา</span>{suspects.length > 1 && <button type="button" className="btn btn-sm btn-danger py-0 px-2" onClick={() => setSuspects((p) => p.filter((_, idx) => idx !== i))}>ลบ</button>}</div>
                  <div className="row g-2">
                    <div className="col-12"><input type="text" className="form-control form-control-sm" placeholder="ชื่อ-สกุล" value={s.name} onChange={(e) => su('name', e.target.value)} /></div>
                    <div className="col-12 col-md-6"><input type="text" className="form-control form-control-sm" placeholder="เลขบัตร ปชช/พาสปอร์ต" value={s.idCard} onChange={(e) => su('idCard', e.target.value)} /></div>
                    <div className="col-12 col-md-3"><input type="text" className="form-control form-control-sm" placeholder="สัญชาติ" value={s.nat} onChange={(e) => su('nat', e.target.value)} /></div>
                    <div className="col-12 col-md-3"><input type="number" className="form-control form-control-sm" placeholder="อายุ (ปี)" value={s.age} onChange={(e) => su('age', e.target.value)} /></div>
                    <div className="col-12"><input type="text" className="form-control form-control-sm" placeholder="ที่อยู่" value={s.address} onChange={(e) => su('address', e.target.value)} /></div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Charges */}
          <div className="col-12" style={{ background: 'rgba(255, 193, 7, 0.1)', padding: 15, borderRadius: 10, marginTop: 15 }}>
            <div className="d-flex justify-content-between align-items-center mb-2 gap-2 flex-wrap"><label className="small text-warning fw-bold"><i className="fa-solid fa-gavel"></i> ข้อหา</label><div className="d-flex gap-2"><ChargeGroupToggle grouped={groupCharges} onToggle={() => setGroupCharges((v) => !v)} disabled={!chargeGroups.length} /><button type="button" className="btn btn-sm btn-warning" onClick={() => setChargeRows((p) => [...p, { value: '', other: '' }])}><i className="fa-solid fa-plus"></i> เพิ่มข้อหา</button></div></div>
            {chargeRows.map((c, i) => {
              const cu = (patch: Partial<{ value: string; other: string }>) => setChargeRows((p) => p.map((x, idx) => (idx === i ? { ...x, ...patch } : x)));
              return (
                <div className="row g-2 mb-2" key={i}>
                  <div className="col-10">
                    <ChargeSelect value={c.value} onChange={(v) => cu({ value: v })} groups={chargeGroups} flat={charges} grouped={groupCharges} allowOther />
                    {c.value === '__OTHER__' && <input type="text" className="form-control border-warning mt-1" placeholder="พิมพ์ข้อหา..." value={c.other} onChange={(e) => cu({ other: e.target.value })} />}
                  </div>
                  <div className="col-2 text-end"><button type="button" className="btn btn-sm btn-outline-danger w-100" onClick={() => setChargeRows((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i></button></div>
                </div>
              );
            })}
          </div>

          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12"><label className="form-label small text-white-50">สถานที่จับกุม/เกิดเหตุ</label><input type="text" className="form-control" value={f.location} onChange={(e) => set('location', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ละติจูด (Latitude)</label><input type="text" className="form-control" value={f.lat} onChange={(e) => set('lat', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ลองจิจูด (Longitude)</label><input type="text" className="form-control" value={f.lng} onChange={(e) => set('lng', e.target.value)} /></div>
          <div className="col-6 col-md-2 d-flex align-items-end"><button type="button" className="btn btn-outline-success w-100" onClick={() => {
            if (!navigator.geolocation) return;
            loadingModal('กำลังดึงพิกัด...');
            navigator.geolocation.getCurrentPosition((pos) => { setF((p) => ({ ...p, lat: String(pos.coords.latitude), lng: String(pos.coords.longitude) })); Swal.close(); }, () => Swal.fire('ผิดพลาด', 'ดึงพิกัดไม่สำเร็จ', 'error'), { enableHighAccuracy: true });
          }}><i className="fa-solid fa-location-crosshairs"></i> ระบุพิกัด</button></div>
          {/* จับกุมมักเขียนรายงานย้อนหลังที่หน่วย ไม่ใช่ตรงจุดจับ ปุ่มดึงพิกัดจึงให้ค่าผิดจุด
              ถ้ากดตอนกลับถึงที่ทำงานแล้ว ต้องมีทางปักหมุดเองคู่กันไว้ */}
          <div className="col-6 col-md-2 d-flex align-items-end">
            <LocationPickerButton
              lat={f.lat}
              lng={f.lng}
              title="ปักหมุดจุดจับกุม"
              label="ปักหมุด"
              onSelect={(lat, lng) => setF((p) => ({ ...p, lat, lng }))}
            />
          </div>

          {/* Seized items (structured) */}
          <div className="col-12" style={{ background: 'rgba(25, 135, 84, 0.1)', padding: 15, borderRadius: 10 }}>
            <div className="d-flex justify-content-between mb-2"><label className="small text-success fw-bold"><i className="fa-solid fa-box-open"></i> รายการของกลาง</label><button type="button" className="btn btn-sm btn-success" onClick={() => setSeized((p) => { const n = [...p, { name: '', qty: '', note: '' }]; return n; })}><i className="fa-solid fa-plus"></i> เพิ่มของกลาง</button></div>
            {seized.map((s, i) => {
              const su = (k: keyof Seized, v: string) => setSeized((p) => { const n = p.map((x, idx) => (idx === i ? { ...x, [k]: v } : x)); setTimeout(() => composeItems(n), 0); return n; });
              return (
                <div className="bg-dark p-2 rounded mb-2 border border-secondary" key={i}>
                  <div className="row g-2">
                    <div className="col-12 col-md-5"><input type="text" className="form-control form-control-sm" placeholder="ชื่อของกลาง" value={s.name} onChange={(e) => su('name', e.target.value)} /></div>
                    <div className="col-6 col-md-3"><input type="text" className="form-control form-control-sm" placeholder="จำนวน" value={s.qty} onChange={(e) => su('qty', e.target.value)} /></div>
                    <div className="col-6 col-md-3"><input type="text" className="form-control form-control-sm" placeholder="รายละเอียด" value={s.note} onChange={(e) => su('note', e.target.value)} /></div>
                    <div className="col-12 col-md-1 text-end"><button type="button" className="btn btn-sm btn-outline-danger" onClick={() => setSeized((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i></button></div>
                  </div>
                </div>
              );
            })}
            <div className="small text-white-50">ไม่มีของกลาง = ไม่ต้องเพิ่มรายการ · ระบบจะสรุปข้อความลงช่อง "ของกลาง (ข้อความ)" ให้อัตโนมัติ</div>
          </div>

          <div className="col-12"><label className="form-label small text-white-50">ของกลาง (ข้อความ)</label><textarea className="form-control" rows={2} placeholder="ระบุของกลางที่ยึดได้..." value={f.items} onChange={(e) => { setManualItems(true); set('items', e.target.value); }} /></div>

          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ประเภทคดีบุหรี่ไฟฟ้า</label><select className="form-select" value={f.ecigType} onChange={(e) => set('ecigType', e.target.value)}><option value="">— ไม่ใช่คดีบุหรี่ไฟฟ้า —</option><option value="รายใหญ่">รายใหญ่</option><option value="รอบสถานศึกษา">รอบสถานศึกษา</option><option value="แหล่งท่องเที่ยว">แหล่งท่องเที่ยว</option><option value="รายย่อย">รายย่อย</option></select></div>
          <div className="col-12 col-md-8"><label className="form-label small text-white-50">เว็บไซต์/URL ที่เกี่ยวข้อง</label><input type="text" className="form-control" placeholder="เช่น https://... (เว้นว่างได้)" value={f.relatedUrl} onChange={(e) => set('relatedUrl', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">มูลค่าความเสียหาย (บาท)</label><input type="number" className="form-control" min="0" placeholder="เว้นว่างได้" value={f.damageValue} onChange={(e) => set('damageValue', e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">วงเงินหมุนเวียน (บาท)</label><input type="number" className="form-control" min="0" placeholder="เว้นว่างได้" value={f.turnoverValue} onChange={(e) => set('turnoverValue', e.target.value)} /></div>

          <div className="col-12"><label className="form-label small text-white-50">พฤติการณ์</label><textarea className="form-control" rows={3} placeholder="ระบุพฤติการณ์การจับกุม..." value={f.circumstances} onChange={(e) => set('circumstances', e.target.value)} /></div>
          <div className="col-12"><label className="form-label small text-white-50">การดำเนินการส่งต่อ</label><input type="text" className="form-control" placeholder="เช่น ส่ง พงส.สภ.เมืองตาก ดำเนินคดีตามกฎหมาย" value={f.forwarding} onChange={(e) => set('forwarding', e.target.value)} /></div>

          <div className="col-12 mt-3"><label className="form-label small text-white-50">แนบภาพประกอบ/บันทึกจับกุม (เลือกได้หลายไฟล์)</label><input type="file" className="form-control" multiple accept="image/*,application/pdf" onChange={(e) => setFiles(e.target.files)} /></div>
          <div className="col-12 col-md-6 mt-4"><button type="button" className="btn btn-outline-info w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={generateAutoDocs}><i className="fa-solid fa-file-word"></i> ออกเอกสารจับกุมอัตโนมัติ (ม.22-23)</button></div>
          <div className="col-12 col-md-6 mt-4"><button type="button" className="btn btn-danger w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={submit}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่งรายงาน</button></div>
        </div>
      </div>
    </FormShell>
  );
};
