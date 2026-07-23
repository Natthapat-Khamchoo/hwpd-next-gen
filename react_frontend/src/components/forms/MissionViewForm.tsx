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
  confirmLinePreview,
  showLineCopyResult,
  loadingModal,
} from '../../utils/formHelpers';
import Swal from 'sweetalert2';

const ADMIN_ROLES = ['Station_Admin', 'สิบเวร', 'Division_Commander', 'Division_Admin'];

export const MissionViewForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();
  const { units } = useStationData();
  const isAdmin = ADMIN_ROLES.includes(user?.role || '');
  const [reportDateTime, setReportDateTime] = useState(getNowDateTimeLocal());
  const [unit, setUnit] = useState(isAdmin ? '' : user?.unit || '');
  const [start, setStart] = useState(getNowDateLocal());
  const [end, setEnd] = useState(getNowDateLocal());
  const [missions, setMissions] = useState<any[] | null>(null);

  const search = async () => {
    if (!unit || !start || !end) return Swal.fire('แจ้งเตือน', 'กรุณากรอกข้อมูลการค้นหาให้ครบ', 'warning');
    loadingModal('กำลังดึงข้อมูลภารกิจ...');
    const res = await api.fetchMissions(unit === 'ทุกหน่วย' ? '' : unit, start, end, user?.station || '');
    Swal.close();
    if (res.status === 'success') setMissions(res.data);
    else Swal.fire('ผิดพลาด', res.message || 'ดึงข้อมูลไม่สำเร็จ', 'error');
  };

  const sendSummary = async () => {
    if (!missions) return;
    const st = getFrontendStationData(user?.station);
    const showAll = unit === 'ทุกหน่วย' || unit === '';
    let missionText = missions
      .map((m) => `วันที่ ${m.startTime} น. ${showAll ? `[${m.targetUnits}] ` : ''}ภารกิจ ${m.details}`)
      .join('\n');
    if (!missionText) missionText = '- ไม่มีภารกิจในช่วงเวลาดังกล่าว -';
    const unitHeader = showAll ? 'ทุกหน่วย' : `หน่วย ${unit}`;
    const previewText = `${st.f} สรุปภารกิจ${unitHeader}\nตั้งแต่วันที่ ${formatPreviewDate(start)} ถึงวันที่ ${formatPreviewDate(end)}\nภารกิจ\n${missionText.trim()}`;
    const { confirmed, copied } = await confirmLinePreview(previewText);
    if (!confirmed) return;
    loadingModal('กำลังส่งข้อมูลเข้า LINE...');
    const res = await api.submitReport('mission-summary', { stationId: user?.station, unitName: unit, startDate: start, endDate: end, reportDateTime }, user?.token, { missions });
    await showLineCopyResult(res.message || 'ส่งสรุปภารกิจสำเร็จ', res.lineText || previewText, copied);
    onBack();
  };

  return (
    <FormShell title="เรียกดูภารกิจหน่วย" onBack={onBack} backLabel="กลับหน้าหลัก">
      <div className="glass-card w-100">
        <div className="row g-3">
          <div className="col-12"><label className="form-label small text-white-50">วันที่เวลาที่เรียกดูข้อมูล</label><input type="datetime-local" className="form-control" value={reportDateTime} onChange={(e) => setReportDateTime(e.target.value)} /></div>
          <div className="col-12"><hr className="border-secondary" /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ภารกิจของหน่วยบริการ</label>
            <select className="form-select border-info" value={unit} onChange={(e) => setUnit(e.target.value)} disabled={!isAdmin}>
              {isAdmin ? (
                <>
                  <option value="">-- เลือกหน่วยบริการ --</option>
                  <option value="ทุกหน่วย">ดูทุกหน่วยของสถานี {user?.station}</option>
                  {units.map((u) => <option key={u} value={u}>{u}</option>)}
                </>
              ) : (
                <option value={user?.unit}>{user?.unit}</option>
              )}
            </select>
          </div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">เรียกข้อมูลตั้งแต่</label><input type="date" className="form-control" value={start} onChange={(e) => setStart(e.target.value)} /></div>
          <div className="col-12 col-md-4"><label className="form-label small text-white-50">ถึงวันที่</label><input type="date" className="form-control" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
          <div className="col-12 mt-4"><button type="button" className="btn btn-info w-100 fw-bold" onClick={search}><i className="fa-solid fa-magnifying-glass"></i> ค้นหาภารกิจ</button></div>

          {missions && (
            <div className="col-12 mt-4">
              <div className="p-3 rounded" style={{ background: 'rgba(0, 242, 255, 0.05)', border: '1px solid rgba(0, 242, 255, 0.3)' }}>
                <h6 className="text-info mb-3"><i className="fa-solid fa-calendar-check"></i> รายการภารกิจที่พบ</h6>
                <div className="mb-3">
                  {missions.length === 0 ? (
                    <div className="text-center text-white-50 py-3">- ไม่พบภารกิจในช่วงเวลาที่เลือก -</div>
                  ) : (
                    <div className="list-group list-group-flush">
                      {missions.map((m, i) => (
                        <div className="list-group-item bg-transparent text-white border-secondary px-0 py-3" key={i}>
                          <div className="text-info fw-bold mb-2"><i className="fa-regular fa-clock"></i> {m.startTime} น.{(unit === 'ทุกหน่วย') && <span className="badge bg-secondary ms-2">{m.targetUnits}</span>}</div>
                          <div className="pe-3 mb-2 text-light" style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', lineHeight: 1.6 }}>{m.details}</div>
                          <div className="small text-white-50 mt-2"><i className="fa-solid fa-location-dot"></i> {m.location}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <button type="button" className="btn-primary-custom mt-2" onClick={sendSummary}><i className="fa-solid fa-paper-plane"></i> ส่งสรุปภารกิจเข้า LINE</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </FormShell>
  );
};
