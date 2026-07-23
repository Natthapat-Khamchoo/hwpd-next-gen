import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useStationData } from '../../hooks/useStationData';
import { FormShell } from './FormShell';
import {
  getNowDateTimeLocal,
  getNowDateLocal,
  getFrontendStationData,
  formatPreviewDate,
  filesToBase64,
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

const cleanUnit = (u: string) => u.replace(/หน่วยบริการฯ?\s*/g, '');
const timePart = (dt: string) => (dt.split('T')[1] || '');

const composeDailyExtraLines = (o: Record<string, any>): string => {
  const n = (k: string) => parseInt(o[k], 10) || 0;
  const lines: string[] = [];
  const smk: string[] = [];
  if (n('smkTransCheck')) smk.push('รถขนส่ง ' + n('smkTransCheck'));
  if (n('smkBusCheck')) smk.push('รถโดยสาร ' + n('smkBusCheck'));
  if (n('smkCarCheck')) smk.push('รถยนต์ ' + n('smkCarCheck'));
  if (n('smkBikeCheck')) smk.push('จยย. ' + n('smkBikeCheck'));
  const smkFail = n('smkTransFail') + n('smkBusFail') + n('smkCarFail') + n('smkBikeFail');
  const smkCancel = n('smkTransCancel') + n('smkBusCancel') + n('smkCarCancel') + n('smkBikeCancel');
  if (smk.length || smkFail || smkCancel || n('smkArrest') || n('smkAdvice')) {
    lines.push('การตรวจมลพิษ/ควันดำ');
    if (smk.length) lines.push('- เรียกตรวจ ' + smk.join(' / ') + ' ครั้ง');
    if (smkFail) lines.push('- ไม่ผ่าน/สั่งห้ามใช้ ' + smkFail + ' คัน');
    if (smkCancel) lines.push('- ยกเลิกคำสั่งห้ามใช้ ' + smkCancel + ' คัน');
    if (n('smkArrest')) lines.push('- จับกุมผู้ขับขี่ ' + n('smkArrest') + ' คน');
    if (n('smkAdvice')) lines.push('- ให้คำแนะนำ ' + n('smkAdvice') + ' ครั้ง');
  }
  const burnParts: string[] = [];
  ([['บุกรุก/เผาป่า', 'burnForest'], ['เกษตรกรเผาไร่', 'burnFarm'], ['โรงงาน', 'factory']] as const).forEach((b) => {
    if (n(b[1] + 'Check') || n(b[1] + 'Arrest') || n(b[1] + 'Advice'))
      burnParts.push(`${b[0]} ตรวจ ${n(b[1] + 'Check')} จับ ${n(b[1] + 'Arrest')} แนะนำ ${n(b[1] + 'Advice')}`);
  });
  if (burnParts.length) lines.push('การเผา/โรงงาน: ' + burnParts.join(' | '));
  const extras: string[] = [];
  if (n('searchTarget') || n('searchSeized')) extras.push(`ตรวจค้นเป้าหมาย ${n('searchTarget')} ครั้ง (พบ/ยึดของกลาง ${n('searchSeized')})`);
  if (n('complaintCount')) extras.push(`รับเรื่องร้องทุกข์ ${n('complaintCount')} เรื่อง`);
  if (n('homeCheck')) extras.push(`ตรวจที่พัก/สถานประกอบการ ${n('homeCheck')} ครั้ง`);
  if (n('vehicleCheck')) extras.push(`ตรวจยานพาหนะ ${n('vehicleCheck')} คัน`);
  if (n('alienRecord')) extras.push(`บันทึกข้อมูลคนต่างด้าว ${n('alienRecord')} คน`);
  if (extras.length) lines.push('การปฏิบัติอื่น: ' + extras.join(', '));
  return lines.length ? '\n' + lines.join('\n') : '';
};

const composeVolunteerLines = (o: Record<string, any>): string => {
  if (o.dutyType !== 'ทำจิตอาสา') return '';
  const n = (k: string) => parseInt(o[k], 10) || 0;
  const lines: string[] = [];
  let typeText = o.volType || '';
  if (typeText && o.volSubType && o.volType === 'จิตอาสาพัฒนา') typeText += ' (' + o.volSubType + ')';
  if (o.volSpecial) typeText += (typeText ? ' · ' : '') + o.volSpecial;
  if (typeText) lines.push('ประเภทจิตอาสา: ' + typeText);
  if (o.volHost === 'ไปเข้าร่วม') lines.push('ลักษณะ: ไปเข้าร่วม' + (o.volHostUnit ? ' (เจ้าภาพ: ' + o.volHostUnit + ')' : ''));
  else if (o.volHost === 'จัดเอง') lines.push('ลักษณะ: จัดเอง');
  const parts: string[] = [];
  if (n('volPolice')) parts.push('ตร. ' + n('volPolice'));
  if (n('volPoliceOther')) parts.push('ตร.หน่วยอื่น ' + n('volPoliceOther'));
  if (n('volGov')) parts.push('ขรก.อื่น ' + n('volGov'));
  if (n('volCivil')) parts.push('ประชาชน ' + n('volCivil'));
  if (parts.length) lines.push('ผู้เข้าร่วม: ' + parts.join(', ') + ' รวม ' + (n('volPolice') + n('volPoliceOther') + n('volGov') + n('volCivil')) + ' คน');
  if (n('volBloodCc') || n('volPlateletUnit')) {
    let b = 'ได้โลหิต ' + n('volBloodCc') + ' ซีซี';
    if (n('volPlateletUnit')) b += ' เกล็ดเลือด ' + n('volPlateletUnit') + ' ยูนิต';
    lines.push(b);
  }
  return lines.length ? '\n' + lines.join('\n') : '';
};

const TABS = [
  { id: 1, icon: 'fa-clipboard-check', label: '1. เวรผลัด' },
  { id: 2, icon: 'fa-chart-pie', label: '2. ผลปฏิบัติ' },
  { id: 3, icon: 'fa-building-shield', label: '3. เวรสิบเวร' },
  { id: 4, icon: 'fa-chart-line', label: '4. สรุปผล' },
  { id: 5, icon: 'fa-car-side', label: '5. ว.4 อื่นๆ' },
];

export const DailyReportForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units, users, charges, phoneMap } = useStationData({ charges: true });
  const [tab, setTab] = useState(1);
  const [files, setFiles] = useState<Record<string, FileList | null>>({});
  const st = getFrontendStationData(user?.station);
  const today = getNowDateLocal();

  // ---------- Tab 1 ----------
  const [t1, setT1] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(), unitId: '', dutyOfficer: '', dutyPhone: '', carNumber: '',
    driverName: '', driverPhone: '', radioOpName: '', radioOpPhone: '', startTime: today, endTime: today,
    camTotal: '0', camReady: '0', camBroken: '0',
  });
  const s1 = (k: string, v: string) => setT1((p) => ({ ...p, [k]: v }));
  const s1user = (k: string, phoneK: string, v: string) => setT1((p) => ({ ...p, [k]: v, [phoneK]: phoneMap[v] || p[phoneK] }));

  const submitT1 = async () => {
    if (!t1.unitId || !t1.dutyOfficer || !t1.driverName || !t1.radioOpName) return Swal.fire('ข้อมูลไม่ครบ', 'กรุณาเลือกหน่วยและกำลังพลให้ครบ', 'warning');
    const cu = cleanUnit(t1.unitId);
    const previewText =
      `หน่วยบริการ ${cu}\nวันที่ ${formatPreviewDate(t1.reportDateTime)}\nปฏิบัติหน้าที่ประจำหน่วยบริการ ${cu}\n` +
      `ยศ ชื่อ สกุล ${t1.dutyOfficer}\nโทร ${t1.dutyPhone}\nรถวิทยุตรวจเขต ${t1.carNumber}\n` +
      `พลขับ ยศ ชื่อ สกุล ${t1.driverName}\nโทร ${t1.driverPhone}\nพงว. ยศ ชื่อ สกุล ${t1.radioOpName}\nโทร ${t1.radioOpPhone}\n` +
      `ปฏิบัติหน้าที่ตั้งแต่เวลา 08.00 น. ของวันที่ ${formatPreviewDate(t1.startTime)} ถึง 08.00 น. ของวันที่ ${formatPreviewDate(t1.endTime)}\n\n` +
      `รายงานสถานะการใช้งานกล้องประจำตัว body worn\n1. กล้อง body worn ได้รับทั้งหมด ${t1.camTotal} ตัว\n` +
      `2. เปิดใช้งานทดสอบระบบ เวลา ${timePart(t1.reportDateTime)} น.\nพร้อมใช้งาน ${t1.camReady} ตัว\n3. ใช้งานไม่ได้ ${t1.camBroken} ตัว\n\n` +
      `จึงเรียนมาเพื่อโปรดทราบ\n( ${cu} )\n( ${st.f} )\n\nไฟล์หลักฐาน: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึก...');
    const res = await api.submitReport('daily', { ...t1, unitName: 'หน่วยบริการฯ ' + t1.unitId, stationId: user?.station, actionBy: user?.username }, user?.token, { files: await filesToBase64(files.f1) });
    if (res.status === 'success') { await showLineCopyResult(res.message || 'บันทึกสำเร็จ', res.lineText || previewText, copied); onBack(); }
    else Swal.fire('เกิดข้อผิดพลาด!', res.message || 'บันทึกไม่สำเร็จ', 'error');
  };

  // ---------- Tab 2 ----------
  const NUM2_DEFAULTS: Record<string, string> = {};
  ['v43', 'service', 'v42', 'v20', 'camTotal2', 'camReady2', 'camBroken2',
    'smkTransCheck', 'smkTransFail', 'smkTransCancel', 'smkBusCheck', 'smkBusFail', 'smkBusCancel',
    'smkCarCheck', 'smkCarFail', 'smkCarCancel', 'smkBikeCheck', 'smkBikeFail', 'smkBikeCancel', 'smkArrest', 'smkAdvice',
    'burnForestCheck', 'burnForestArrest', 'burnForestAdvice', 'burnFarmCheck', 'burnFarmArrest', 'burnFarmAdvice',
    'factoryCheck', 'factoryArrest', 'factoryAdvice', 'searchTarget', 'searchSeized', 'complaintCount', 'homeCheck', 'vehicleCheck', 'alienRecord',
  ].forEach((k) => (NUM2_DEFAULTS[k] = '0'));
  const [t2, setT2] = useState<Record<string, string>>({ unitId: '', reportDateTime: getNowDateTimeLocal(), ...NUM2_DEFAULTS });
  const s2 = (k: string, v: string) => setT2((p) => ({ ...p, [k]: v }));
  const [chargeRows, setChargeRows] = useState<{ name: string; amount: string }[]>([]);
  const [showSmoke, setShowSmoke] = useState(false);
  const [showExtra, setShowExtra] = useState(false);
  const v20n = parseInt(t2.v20) || 0;

  const submitT2 = async () => {
    if (!t2.unitId) return Swal.fire('ข้อมูลไม่ครบ', 'กรุณาเลือกหน่วยบริการ', 'warning');
    const validCharges = chargeRows.filter((c) => c.name && c.amount);
    if (v20n > 0 && validCharges.length === 0) return Swal.fire('แจ้งเตือน', 'คุณมียอด ว.20 กรุณาระบุรายการข้อหาอย่างน้อย 1 ข้อหาครับ', 'warning');
    const cu = cleanUnit(t2.unitId);
    const previewText =
      `หน่วยบริการ ${cu}\n\nวันที่ ${formatPreviewDate(t2.reportDateTime)}\nการดำเนินการ\nว.43 = ${t2.v43}\nบริการ = ${t2.service}\nว.42 = ${t2.v42}\nว.20 = ${t2.v20}\n\n` +
      `รายงานสถานะการใช้งานกล้องประจำตัว body worn\n1.กล้อง body worn ได้รับทั้งหมด ${t2.camTotal2} ตัว\n2. เปิดใช้งานทดสอบระบบ\nเวลา ${timePart(t2.reportDateTime)} น.\nพร้อมใช้งาน ${t2.camReady2} ตัว\n3.ใช้งานไม่ได้ ${t2.camBroken2} ตัว\n${composeDailyExtraLines(t2)}\nเหตุการณ์ทั่วไปปกติ\n\nไฟล์หลักฐาน: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึก...');
    const res = await api.submitReport('daily-result', { ...t2, unitName: 'หน่วยบริการฯ ' + t2.unitId, stationId: user?.station, actionBy: user?.username }, user?.token, { files: await filesToBase64(files.f2), charges: validCharges });
    if (res.status === 'success') { await showLineCopyResult(res.message || 'บันทึกสำเร็จ', res.lineText || previewText, copied); onBack(); }
    else Swal.fire('เกิดข้อผิดพลาด!', res.message || 'บันทึกไม่สำเร็จ', 'error');
  };

  // ---------- Tab 3 ----------
  const [t3, setT3] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(), inspectorName: '', inspectorPhone: '', dutyOfficerName: '', dutyOfficerPhone: '',
    radioOpName: '', radioOpPhone: '', startTime: today, endTime: today,
  });
  const s3 = (k: string, v: string) => setT3((p) => ({ ...p, [k]: v }));
  const s3user = (k: string, phoneK: string, v: string) => setT3((p) => ({ ...p, [k]: v, [phoneK]: phoneMap[v] || p[phoneK] }));
  const submitT3 = async () => {
    if (!t3.inspectorName || !t3.dutyOfficerName || !t3.radioOpName) return Swal.fire('ข้อมูลไม่ครบ', 'กรุณาเลือกกำลังพลให้ครบ', 'warning');
    const previewText =
      `รายงานประจำวัน ${st.f}\nวันที่ ${formatPreviewDate(t3.reportDateTime)}\nร้อยเวร ${t3.inspectorName} โทร ${t3.inspectorPhone}\n` +
      `สิบเวร ${t3.dutyOfficerName} โทร ${t3.dutyOfficerPhone}\nพงว. ${t3.radioOpName} โทร ${t3.radioOpPhone}\n` +
      `ปฏิบัติหน้าที่ตั้งแต่เวลา 08.00 น. ของวันที่ ${formatPreviewDate(t3.startTime)} ถึง 08.00 น. ของวันที่ ${formatPreviewDate(t3.endTime)}\n\nจึงเรียนมาเพื่อโปรดทราบ`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังส่ง...');
    const res = await api.submitReport('station-duty', { ...t3, unitId: user?.unit, stationId: user?.station, actionBy: user?.username }, user?.token);
    if (res.status === 'success') { await showLineCopyResult(res.message || 'บันทึกสำเร็จ', res.lineText || previewText, copied); onBack(); }
    else Swal.fire('เกิดข้อผิดพลาด!', res.message || 'บันทึกไม่สำเร็จ', 'error');
  };

  // ---------- Tab 4 ----------
  const [t4, setT4] = useState<Record<string, string>>({ reportDateTime: getNowDateTimeLocal(), startDate: today, endDate: today });
  const [summary, setSummary] = useState<any | null>(null);
  const fetchSummary = async () => {
    if (!t4.startDate || !t4.endDate) return Swal.fire('แจ้งเตือน', 'เลือกวันที่ให้ครบ', 'warning');
    loadingModal('กำลังคำนวณ...');
    const res = await api.getDailySummary(user?.station || '', t4.startDate, t4.endDate);
    Swal.close();
    if (res.status === 'success') setSummary(res.data);
    else Swal.fire('ผิดพลาด', res.message || 'ดึงข้อมูลไม่สำเร็จ', 'error');
  };
  const submitT4 = async () => {
    if (!t4.reportDateTime || !summary) return Swal.fire('แจ้งเตือน', 'ระบุวันที่รายงานและดึงข้อมูลก่อน', 'warning');
    const chargeSection = summary.chargesText && summary.chargesText.trim() ? `แบ่งเป็น\n${summary.chargesText.trim()}` : '';
    const previewText = `${st.f} สรุปผลการปฏิบัติประจำวัน\nวันที่ ${formatPreviewDate(t4.reportDateTime)}\nการดำเนินการ\nว.43 = ${summary.v43}\nบริการ = ${summary.service}\nว.42 = ${summary.v42}\nว.20 = ${summary.v20}\n${chargeSection}`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังส่ง...');
    const res = await api.submitReport('daily-summary', { stationId: user?.station, reportDateTime: t4.reportDateTime, ...summary }, user?.token);
    if (res.status === 'success') { await showLineCopyResult(res.message || 'ส่งสรุปสำเร็จ', res.lineText || previewText, copied); onBack(); }
    else Swal.fire('เกิดข้อผิดพลาด!', res.message || 'ส่งไม่สำเร็จ', 'error');
  };

  // ---------- Tab 5 ----------
  const [t5, setT5] = useState<Record<string, string>>({
    reportDateTime: getNowDateTimeLocal(), unitId: '', carNumber: '', dutyType: '', dutyOtherText: '', actionDetails: '', location: '',
    volType: '', volSubType: '', volSpecial: '', volHost: '', volHostUnit: '', volPolice: '0', volPoliceOther: '0', volGov: '0', volCivil: '0', volBloodCc: '0', volPlateletUnit: '0',
  });
  const s5 = (k: string, v: string) => setT5((p) => ({ ...p, [k]: v }));
  const [officers, setOfficers] = useState<string[]>(['']);
  const submitT5 = async () => {
    const offs = officers.filter(Boolean);
    if (offs.length === 0) return Swal.fire('แจ้งเตือน', 'เพิ่มเจ้าหน้าที่อย่างน้อย 1 นาย', 'warning');
    if (!t5.unitId || !t5.carNumber || !t5.dutyType || !t5.actionDetails || !t5.location) return Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกข้อมูลให้ครบ', 'warning');
    const dutyDisplay = t5.dutyType === 'อื่นๆ' ? t5.dutyOtherText : t5.dutyType;
    const officersText = offs.map((name, i) => `${i + 1}. ${name}`).join('  ');
    const previewText =
      `${st.f}\nเรียน ผู้บังคับบัญชา\nวันที่ ${formatPreviewDate(t5.reportDateTime)}\nหน่วยบริการประชาชนตำรวจทางหลวง${t5.unitId}\n` +
      `รถวิทยุ ${t5.carNumber}\nมี ${officersText}\nการปฏิบัติ ${dutyDisplay} ดำเนินการ ${t5.actionDetails}\nณ ${t5.location}${composeVolunteerLines(t5)}\n\n` +
      `จึงเรียนมาเพื่อโปรดทราบ\n             (${st.p})\nไฟล์ประกอบ: [ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังบันทึก...');
    const res = await api.submitReport('other-duty', { ...t5, stationId: user?.station, actionBy: user?.username }, user?.token, { files: await filesToBase64(files.f5), officers: offs });
    if (res.status === 'success') { await showLineCopyResult(res.message || 'บันทึกสำเร็จ', res.lineText || previewText, copied); onBack(); }
    else Swal.fire('เกิดข้อผิดพลาด!', res.message || 'บันทึกไม่สำเร็จ', 'error');
  };

  const UnitSelect = ({ value, onChange, border = 'border-info' }: { value: string; onChange: (v: string) => void; border?: string }) => (
    <select className={`form-select ${border}`} value={value} onChange={(e) => onChange(e.target.value)} required>
      <option value="">-- เลือกหน่วยบริการ --</option>
      {units.map((u) => <option key={u} value={u}>{u}</option>)}
    </select>
  );
  const UserSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select className="form-select" value={value} onChange={(e) => onChange(e.target.value)} required>
      <option value="">-- เลือกรายชื่อ --</option>
      {users.map((u) => <option key={u} value={u}>{u}</option>)}
    </select>
  );
  const Num2 = ({ k, label, cls = '' }: { k: string; label: string; cls?: string }) => (
    <>
      <label className="form-label small text-white-50">{label}</label>
      <input type="number" className={`form-control text-center ${cls}`} value={t2[k]} onChange={(e) => s2(k, e.target.value)} min="0" />
    </>
  );

  return (
    <FormShell title="หมวดรายงานประจำวัน HWPD" onBack={onBack} maxWidth={900}>
      <ul className="nav nav-pills mb-4 justify-content-center flex-wrap gap-1">
        {TABS.map((t) => (
          <li className="nav-item" key={t.id}>
            <button className={`nav-link ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}><i className={`fa-solid ${t.icon}`}></i> {t.label}</button>
          </li>
        ))}
      </ul>

      {/* TAB 1 */}
      {tab === 1 && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">1. รายงานประจำวัน (เวรผลัด)</h5>
          <div className="row g-3">
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label><div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={t1.reportDateTime} onChange={(e) => s1('reportDateTime', e.target.value)} /><button type="button" className="btn btn-outline-info" onClick={() => s1('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">หน่วยบริการ</label><UnitSelect value={t1.unitId} onChange={(v) => s1('unitId', v)} /></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12 col-md-8"><label className="form-label small text-white-50">ผู้ปฏิบัติหน้าที่ประจำหน่วย</label><UserSelect value={t1.dutyOfficer} onChange={(v) => s1user('dutyOfficer', 'dutyPhone', v)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เบอร์โทรศัพท์</label><input type="tel" className="form-control" placeholder="08x-xxxxxxx" value={t1.dutyPhone} onChange={(e) => s1('dutyPhone', e.target.value)} /></div>
            <div className="col-12"><label className="form-label small text-white-50">รถวิทยุตรวจเขต</label><input type="text" className="form-control" placeholder="เลขรถ" value={t1.carNumber} onChange={(e) => s1('carNumber', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">พลขับ</label><UserSelect value={t1.driverName} onChange={(v) => s1user('driverName', 'driverPhone', v)} /><input type="tel" className="form-control mt-2" placeholder="เบอร์โทรพลขับ" value={t1.driverPhone} onChange={(e) => s1('driverPhone', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">พนักงานวิทยุ</label><UserSelect value={t1.radioOpName} onChange={(v) => s1user('radioOpName', 'radioOpPhone', v)} /><input type="tel" className="form-control mt-2" placeholder="เบอร์โทรพงว." value={t1.radioOpPhone} onChange={(e) => s1('radioOpPhone', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ปฏิบัติหน้าที่ตั้งแต่ (ว/ด/ป)</label><input type="date" className="form-control" value={t1.startTime} onChange={(e) => s1('startTime', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ถึงวันที่ (ว/ด/ป)</label><input type="date" className="form-control" value={t1.endTime} onChange={(e) => s1('endTime', e.target.value)} /></div>
            <div className="col-12"><span className="badge bg-info">กล้อง Bodyworn</span></div>
            <div className="col-4"><label className="small text-white-50">ทั้งหมด</label><input type="number" className="form-control text-center" value={t1.camTotal} onChange={(e) => s1('camTotal', e.target.value)} /></div>
            <div className="col-4"><label className="small text-white-50">พร้อมใช้</label><input type="number" className="form-control text-center" value={t1.camReady} onChange={(e) => s1('camReady', e.target.value)} /></div>
            <div className="col-4"><label className="small text-white-50">เสีย</label><input type="number" className="form-control text-center" value={t1.camBroken} onChange={(e) => s1('camBroken', e.target.value)} /></div>
            <div className="col-12"><label className="form-label small text-white-50">แนบไฟล์หลักฐาน</label><input type="file" className="form-control" multiple accept="image/*,video/*,application/pdf" onChange={(e) => setFiles((p) => ({ ...p, f1: e.target.files }))} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn-primary-custom" onClick={submitT1}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button></div>
          </div>
        </div>
      )}

      {/* TAB 2 */}
      {tab === 2 && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">2. ผลการปฏิบัติประจำวัน</h5>
          <div className="row g-3">
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">หน่วยบริการ</label><UnitSelect value={t2.unitId} onChange={(v) => s2('unitId', v)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label><div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={t2.reportDateTime} onChange={(e) => s2('reportDateTime', e.target.value)} /><button type="button" className="btn btn-outline-info" onClick={() => s2('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-md-3 col-6"><Num2 k="v43" label="ว.43 (ครั้ง)" /></div>
            <div className="col-md-3 col-6"><Num2 k="service" label="บริการ (ครั้ง)" /></div>
            <div className="col-md-3 col-6"><Num2 k="v42" label="ว.42 (ครั้ง)" /></div>
            <div className="col-md-3 col-6"><label className="form-label small text-warning fw-bold">ว.20 (ครั้ง)</label><input type="number" className="form-control text-center border-warning" value={t2.v20} onChange={(e) => s2('v20', e.target.value)} min="0" /></div>
            {v20n > 0 && (
              <div className="col-12" style={{ background: 'rgba(255,193,7,0.1)', padding: 15, borderRadius: 10, border: '1px solid rgba(255,193,7,0.3)' }}>
                <div className="d-flex justify-content-between align-items-center mb-2"><label className="small text-warning">รายการข้อหา ว.20</label><button type="button" className="btn btn-sm btn-warning" onClick={() => setChargeRows((p) => [...p, { name: '', amount: '1' }])}><i className="fa-solid fa-plus"></i> เพิ่มข้อหา</button></div>
                {chargeRows.map((c, i) => (
                  <div className="d-flex gap-2 mb-2" key={i}>
                    <select className="form-select border-warning" value={c.name} onChange={(e) => setChargeRows((p) => p.map((x, idx) => (idx === i ? { ...x, name: e.target.value } : x)))}><option value="">-- เลือกข้อหา --</option>{charges.map((ch) => <option key={ch} value={ch}>{ch}</option>)}</select>
                    <input type="number" className="form-control text-center" style={{ width: 80 }} value={c.amount} min="1" onChange={(e) => setChargeRows((p) => p.map((x, idx) => (idx === i ? { ...x, amount: e.target.value } : x)))} />
                    <button type="button" className="btn btn-outline-danger" onClick={() => setChargeRows((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i></button>
                  </div>
                ))}
              </div>
            )}
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12"><span className="badge bg-info">รายงานกล้อง Bodyworn</span></div>
            <div className="col-4"><Num2 k="camTotal2" label="ทั้งหมด" /></div>
            <div className="col-4"><Num2 k="camReady2" label="พร้อมใช้" /></div>
            <div className="col-4"><Num2 k="camBroken2" label="เสีย" /></div>

            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12"><button type="button" className="btn btn-outline-info btn-sm w-100" onClick={() => setShowSmoke((v) => !v)}><i className="fa-solid fa-smog"></i> การตรวจมลพิษ/ควันดำ + เผาป่า/โรงงาน (กดเพื่อเปิด-ปิด)</button></div>
            {showSmoke && (
              <div className="col-12" style={{ background: 'rgba(13,202,240,0.08)', padding: 15, borderRadius: 10, border: '1px solid rgba(13,202,240,0.3)' }}>
                <span className="badge bg-info mb-2">ควันดำ: เรียกตรวจยานพาหนะ</span>
                <div className="row g-2 small text-white-50 mb-1"><div className="col-3"></div><div className="col-3 text-center">เรียกตรวจ</div><div className="col-3 text-center">ไม่ผ่าน</div><div className="col-3 text-center">ยกเลิกห้าม</div></div>
                {([['รถขนส่ง', 'smkTrans'], ['รถโดยสาร', 'smkBus'], ['รถยนต์', 'smkCar'], ['รถ จยย.', 'smkBike']] as const).map(([label, pre]) => (
                  <div className="row g-2 align-items-center mb-1" key={pre}>
                    <div className="col-3 small">{label}</div>
                    {['Check', 'Fail', 'Cancel'].map((suf) => <div className="col-3" key={suf}><input type="number" className="form-control form-control-sm text-center" min="0" value={t2[pre + suf]} onChange={(e) => s2(pre + suf, e.target.value)} /></div>)}
                  </div>
                ))}
                <div className="row g-2 mb-2 mt-1">
                  <div className="col-6"><label className="small text-white-50">จับกุมผู้ขับขี่ (คน)</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t2.smkArrest} onChange={(e) => s2('smkArrest', e.target.value)} /></div>
                  <div className="col-6"><label className="small text-white-50">ให้คำแนะนำ (ครั้ง)</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t2.smkAdvice} onChange={(e) => s2('smkAdvice', e.target.value)} /></div>
                </div>
                <span className="badge bg-info mb-2 mt-2">การเผา/โรงงานปล่อยมลพิษ</span>
                <div className="row g-2 small text-white-50 mb-1"><div className="col-3"></div><div className="col-3 text-center">ตรวจสอบ</div><div className="col-3 text-center">จับกุม</div><div className="col-3 text-center">แนะนำ</div></div>
                {([['บุกรุก/เผาป่า', 'burnForest'], ['เกษตรกรเผาไร่', 'burnFarm'], ['โรงงาน/ผู้ประกอบการ', 'factory']] as const).map(([label, pre]) => (
                  <div className="row g-2 align-items-center mb-1" key={pre}>
                    <div className="col-3 small">{label}</div>
                    {['Check', 'Arrest', 'Advice'].map((suf) => <div className="col-3" key={suf}><input type="number" className="form-control form-control-sm text-center" min="0" value={t2[pre + suf]} onChange={(e) => s2(pre + suf, e.target.value)} /></div>)}
                  </div>
                ))}
              </div>
            )}

            <div className="col-12"><button type="button" className="btn btn-outline-info btn-sm w-100" onClick={() => setShowExtra((v) => !v)}><i className="fa-solid fa-magnifying-glass"></i> ตรวจค้น / เรื่องร้องทุกข์ / ตรวจคนต่างด้าว (กดเพื่อเปิด-ปิด)</button></div>
            {showExtra && (
              <div className="col-12" style={{ background: 'rgba(13,202,240,0.08)', padding: 15, borderRadius: 10, border: '1px solid rgba(13,202,240,0.3)' }}>
                <div className="row g-2">
                  {([['ตรวจค้นเป้าหมาย (ครั้ง)', 'searchTarget'], ['ตรวจค้นพบ/ยึดของกลาง (ครั้ง)', 'searchSeized'], ['รับเรื่องร้องทุกข์ (เรื่อง)', 'complaintCount'], ['ตรวจที่พัก/สถานประกอบการ (ครั้ง)', 'homeCheck'], ['ตรวจยานพาหนะ (คัน)', 'vehicleCheck'], ['บันทึกข้อมูลคนต่างด้าว (คน)', 'alienRecord']] as const).map(([label, k]) => (
                    <div className="col-md-4 col-6" key={k}><label className="small text-white-50">{label}</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t2[k]} onChange={(e) => s2(k, e.target.value)} /></div>
                  ))}
                </div>
              </div>
            )}

            <div className="col-12 mt-3"><label className="form-label small text-white-50">แนบไฟล์หลักฐาน</label><input type="file" className="form-control" multiple accept="image/*,video/*,application/pdf" onChange={(e) => setFiles((p) => ({ ...p, f2: e.target.files }))} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn-primary-custom" onClick={submitT2}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button></div>
          </div>
        </div>
      )}

      {/* TAB 3 */}
      {tab === 3 && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">3. รายงานประจำวันสิบเวร</h5>
          <div className="row g-3">
            <div className="col-12"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label><div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={t3.reportDateTime} onChange={(e) => s3('reportDateTime', e.target.value)} /><button type="button" className="btn btn-outline-info" onClick={() => s3('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12 col-md-8"><label className="form-label small text-white-50">ร้อยเวรฯ</label><UserSelect value={t3.inspectorName} onChange={(v) => s3user('inspectorName', 'inspectorPhone', v)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เบอร์โทรศัพท์</label><input type="tel" className="form-control" value={t3.inspectorPhone} onChange={(e) => s3('inspectorPhone', e.target.value)} /></div>
            <div className="col-12 col-md-8"><label className="form-label small text-white-50">สิบเวร</label><UserSelect value={t3.dutyOfficerName} onChange={(v) => s3user('dutyOfficerName', 'dutyOfficerPhone', v)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เบอร์โทรศัพท์</label><input type="tel" className="form-control" value={t3.dutyOfficerPhone} onChange={(e) => s3('dutyOfficerPhone', e.target.value)} /></div>
            <div className="col-12 col-md-8"><label className="form-label small text-white-50">พนักงานวิทยุ</label><UserSelect value={t3.radioOpName} onChange={(v) => s3user('radioOpName', 'radioOpPhone', v)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">เบอร์โทรศัพท์</label><input type="tel" className="form-control" value={t3.radioOpPhone} onChange={(e) => s3('radioOpPhone', e.target.value)} /></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ปฏิบัติหน้าที่ตั้งแต่ (ว/ด/ป)</label><input type="date" className="form-control" value={t3.startTime} onChange={(e) => s3('startTime', e.target.value)} /></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">ถึงวันที่ (ว/ด/ป)</label><input type="date" className="form-control" value={t3.endTime} onChange={(e) => s3('endTime', e.target.value)} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn-primary-custom" onClick={submitT3}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button></div>
          </div>
        </div>
      )}

      {/* TAB 4 */}
      {tab === 4 && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">4. สรุปผลประจำวัน (Auto-Summary)</h5>
          <div className="row g-3">
            <div className="col-12"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label><div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={t4.reportDateTime} onChange={(e) => setT4((p) => ({ ...p, reportDateTime: e.target.value }))} /><button type="button" className="btn btn-outline-info" onClick={() => setT4((p) => ({ ...p, reportDateTime: getNowDateTimeLocal() }))}><i className="fa-solid fa-clock-rotate-left"></i></button></div></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12"><span className="badge bg-warning text-dark mb-2">กำหนดช่วงเวลาที่ต้องการดึงข้อมูลสรุป</span></div>
            <div className="col-12 col-md-5"><label className="form-label small text-white-50">เรียกข้อมูลตั้งแต่</label><input type="date" className="form-control" value={t4.startDate} onChange={(e) => setT4((p) => ({ ...p, startDate: e.target.value }))} /></div>
            <div className="col-12 col-md-5"><label className="form-label small text-white-50">ถึงวันที่</label><input type="date" className="form-control" value={t4.endDate} onChange={(e) => setT4((p) => ({ ...p, endDate: e.target.value }))} /></div>
            <div className="col-12 col-md-2 d-flex align-items-end"><button type="button" className="btn btn-warning w-100 fw-bold" onClick={fetchSummary}>ดึงข้อมูล <i className="fa-solid fa-sync"></i></button></div>
            {summary && (
              <div className="col-12 mt-4">
                <div className="p-3 rounded" style={{ background: 'rgba(0, 242, 255, 0.1)', border: '1px solid var(--neon-blue)' }}>
                  <h6 className="text-neon mb-3"><i className="fa-solid fa-calculator"></i> ผลการคำนวณยอดรวมสถานี</h6>
                  <div className="row text-center mb-3">
                    <div className="col-3"><div className="small text-white-50">ว.43</div><h5 className="m-0">{summary.v43}</h5></div>
                    <div className="col-3"><div className="small text-white-50">บริการ</div><h5 className="m-0">{summary.service}</h5></div>
                    <div className="col-3"><div className="small text-white-50">ว.42</div><h5 className="m-0">{summary.v42}</h5></div>
                    <div className="col-3"><div className="small text-white-50 text-warning">ว.20</div><h5 className="m-0 text-warning">{summary.v20}</h5></div>
                  </div>
                  <div className="small text-white-50">สรุปข้อหา ว.20:</div>
                  <pre className="text-white bg-dark p-2 rounded" style={{ whiteSpace: 'pre-wrap', fontFamily: 'Kanit', fontSize: '0.9rem' }}>{summary.chargesText || 'ไม่มีข้อมูลข้อหา'}</pre>
                  <button type="button" className="btn-primary-custom mt-2" onClick={submitT4}><i className="fa-solid fa-paper-plane"></i> ยืนยันส่งสรุปผลเข้า LINE</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5 */}
      {tab === 5 && (
        <div className="glass-card w-100">
          <h5 className="text-center text-info mb-4">5. รายงาน ว.4 อื่นๆ</h5>
          <div className="row g-3">
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label><div className="d-flex gap-2"><input type="datetime-local" className="form-control" value={t5.reportDateTime} onChange={(e) => s5('reportDateTime', e.target.value)} /><button type="button" className="btn btn-outline-info" onClick={() => s5('reportDateTime', getNowDateTimeLocal())}><i className="fa-solid fa-clock-rotate-left"></i></button></div></div>
            <div className="col-12 col-md-6"><label className="form-label small text-white-50">หน่วยบริการ</label><UnitSelect value={t5.unitId} onChange={(v) => s5('unitId', v)} /></div>
            <div className="col-12"><hr className="border-secondary" /></div>
            <div className="col-12" style={{ background: 'rgba(0, 242, 255, 0.05)', padding: 15, borderRadius: 10, border: '1px dashed rgba(0, 242, 255, 0.3)' }}>
              <div className="d-flex justify-content-between align-items-center mb-2"><label className="small text-info">รายชื่อเจ้าหน้าที่ผู้ปฏิบัติ</label><button type="button" className="btn btn-sm btn-outline-info" onClick={() => setOfficers((p) => [...p, ''])}><i className="fa-solid fa-user-plus"></i> เพิ่มเจ้าหน้าที่</button></div>
              {officers.map((o, i) => (
                <div className="d-flex gap-2 mb-2" key={i}>
                  <select className="form-select border-info" value={o} onChange={(e) => setOfficers((p) => p.map((x, idx) => (idx === i ? e.target.value : x)))}><option value="">-- เลือกรายชื่อ --</option>{users.map((u) => <option key={u} value={u}>{u}</option>)}</select>
                  {officers.length > 1 && <button type="button" className="btn btn-outline-danger" onClick={() => setOfficers((p) => p.filter((_, idx) => idx !== i))}><i className="fa-solid fa-trash"></i></button>}
                </div>
              ))}
            </div>
            <div className="col-12 mt-3"><label className="form-label small text-white-50">รถวิทยุตรวจเขต</label><input type="text" className="form-control" placeholder="เช่น 51xx" value={t5.carNumber} onChange={(e) => s5('carNumber', e.target.value)} /></div>
            <div className="col-12 col-md-4"><label className="form-label small text-white-50">การปฏิบัติ</label>
              <select className="form-select" value={t5.dutyType} onChange={(e) => s5('dutyType', e.target.value)}><option value="">-- เลือก --</option><option value="ว.4">ว.4</option><option value="ทำจิตอาสา">ทำจิตอาสา</option><option value="ว.4 ช่วยเหลือประชาชน">ว.4 ช่วยเหลือประชาชน</option><option value="อื่นๆ">อื่นๆ (ระบุ)</option></select>
              {t5.dutyType === 'อื่นๆ' && <input type="text" className="form-control mt-2" placeholder="ระบุการปฏิบัติอื่นๆ" value={t5.dutyOtherText} onChange={(e) => s5('dutyOtherText', e.target.value)} />}
            </div>
            <div className="col-12 col-md-8"><label className="form-label small text-white-50">การดำเนินการ</label><textarea className="form-control" rows={2} placeholder="รายละเอียด..." value={t5.actionDetails} onChange={(e) => s5('actionDetails', e.target.value)} /></div>

            {t5.dutyType === 'ทำจิตอาสา' && (
              <div className="col-12" style={{ background: 'rgba(255,193,7,0.08)', padding: 15, borderRadius: 10, border: '1px solid rgba(255,193,7,0.3)' }}>
                <span className="badge bg-warning text-dark mb-2">รายละเอียดจิตอาสา (กรอกเท่าที่มีข้อมูล)</span>
                <div className="row g-2">
                  <div className="col-md-4 col-6"><label className="small text-white-50">ประเภทกิจกรรม</label><select className="form-select form-select-sm" value={t5.volType} onChange={(e) => s5('volType', e.target.value)}><option value="">— ไม่ระบุ —</option><option value="จิตอาสาพัฒนา">จิตอาสาพัฒนา</option><option value="จิตอาสาภัยพิบัติ">จิตอาสาภัยพิบัติ</option><option value="จิตอาสาเฉพาะกิจ">จิตอาสาเฉพาะกิจ</option></select></div>
                  {t5.volType === 'จิตอาสาพัฒนา' && <div className="col-md-4 col-6"><label className="small text-white-50">ประเภทย่อย</label><select className="form-select form-select-sm" value={t5.volSubType} onChange={(e) => s5('volSubType', e.target.value)}><option value="">— ไม่ระบุ —</option><option value="จราจร">จราจร</option><option value="ปรับภูมิทัศน์">ปรับภูมิทัศน์</option><option value="ดูแลรักษาแหล่งน้ำ">ดูแลรักษาแหล่งน้ำ</option><option value="อื่นๆ">อื่นๆ</option></select></div>}
                  <div className="col-md-4 col-6"><label className="small text-white-50">หมวดพิเศษ</label><select className="form-select form-select-sm" value={t5.volSpecial} onChange={(e) => s5('volSpecial', e.target.value)}><option value="">— ไม่มี —</option><option value="บริจาคโลหิต">บริจาคโลหิต</option><option value="PM 2.5">PM 2.5</option></select></div>
                  <div className="col-md-4 col-6"><label className="small text-white-50">ลักษณะการจัด</label><select className="form-select form-select-sm" value={t5.volHost} onChange={(e) => s5('volHost', e.target.value)}><option value="">— ไม่ระบุ —</option><option value="จัดเอง">จัดเอง</option><option value="ไปเข้าร่วม">ไปเข้าร่วม</option></select></div>
                  {t5.volHost === 'ไปเข้าร่วม' && <div className="col-12 col-md-8"><label className="small text-white-50">หน่วยเจ้าภาพ</label><input type="text" className="form-control form-control-sm" placeholder="เช่น อบต.../เทศบาล..." value={t5.volHostUnit} onChange={(e) => s5('volHostUnit', e.target.value)} /></div>}
                </div>
                <label className="small text-white-50 mt-2 d-block">จำนวนผู้เข้าร่วม (คน)</label>
                <div className="row g-2">
                  {([['ตร. หน่วยเรา', 'volPolice'], ['ตร. หน่วยอื่น', 'volPoliceOther'], ['ข้าราชการอื่น', 'volGov'], ['ประชาชน', 'volCivil']] as const).map(([label, k]) => (
                    <div className="col-md-3 col-6" key={k}><label className="small text-white-50">{label}</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t5[k]} onChange={(e) => s5(k, e.target.value)} /></div>
                  ))}
                </div>
                {t5.volSpecial === 'บริจาคโลหิต' && (
                  <div className="row g-2 mt-1">
                    <div className="col-md-3 col-6"><label className="small text-white-50">จำนวนเลือด (ซีซี)</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t5.volBloodCc} onChange={(e) => s5('volBloodCc', e.target.value)} /></div>
                    <div className="col-md-3 col-6"><label className="small text-white-50">เกล็ดเลือด (ยูนิต)</label><input type="number" className="form-control form-control-sm text-center" min="0" value={t5.volPlateletUnit} onChange={(e) => s5('volPlateletUnit', e.target.value)} /></div>
                  </div>
                )}
              </div>
            )}

            <div className="col-12"><label className="form-label small text-white-50">สถานที่ (ณ)</label><input type="text" className="form-control" placeholder="สถานที่ปฏิบัติงาน" value={t5.location} onChange={(e) => s5('location', e.target.value)} /></div>
            <div className="col-12 mt-3"><label className="form-label small text-white-50">แนบไฟล์ประกอบ</label><input type="file" className="form-control" multiple accept="image/*,video/*" onChange={(e) => setFiles((p) => ({ ...p, f5: e.target.files }))} /></div>
            <div className="col-12 mt-4"><button type="button" className="btn-primary-custom" onClick={submitT5}><i className="fa-solid fa-paper-plane"></i> ตรวจสอบข้อมูลก่อนส่ง</button></div>
          </div>
        </div>
      )}
    </FormShell>
  );
};
