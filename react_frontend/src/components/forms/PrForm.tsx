import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { useFormDraft } from '../../hooks/useFormDraft';
import { FormShell } from './FormShell';
import { DraftNotice } from './DraftNotice';
import { ThaiDateInput } from './ThaiDateInput';
import { inspectFiles, MIN_SHORT_EDGE, type MediaMeta } from '../../utils/mediaQc';
import { getNowDateTimeLocal, filesToBase64, loadingModal } from '../../utils/formHelpers';
import Swal from 'sweetalert2';

/**
 * ส่งข่าวประชาสัมพันธ์ (requirement ข้อ 13 — FR-01 / FR-02)
 *
 * ของเดิมเมนูนี้เป็นหน้าว่างที่เขียนว่า "อยู่ระหว่างการพัฒนา"
 *
 * ตรวจความละเอียดสื่อทันทีที่เลือกไฟล์ **แต่ไม่บล็อกการส่ง** ไฟล์ที่ต่ำกว่า 1080p
 * ทำให้ข่าวติดธงรอแอดมินพิจารณา (BR-01) ไม่ใช่ถูกปฏิเสธทิ้ง การไม่ให้ส่งเลยจะทำให้
 * เจ้าหน้าที่เลิกใช้ระบบแล้วกลับไปส่งข่าวทางไลน์เหมือนเดิม
 */

const NEWS_TYPES = [
  'ผลการจับกุม',
  'อุบัติเหตุ',
  'การอำนวยความสะดวกจราจร',
  'กิจกรรมจิตอาสา',
  'ประกาศแจ้งเตือน',
  'อื่นๆ',
];

export const PrForm: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const { user } = useAuth();

  const blank: Record<string, string> = {
    newsDateTime: getNowDateTimeLocal(),
    title: '',
    newsType: '',
    content: '',
    reporterName: user?.fullName || '',
  };
  const [f, setF, draft] = useFormDraft('pr_news', blank, user?.username);
  const [files, setFiles] = useState<FileList | null>(null);
  const [media, setMedia] = useState<MediaMeta[]>([]);
  const [checking, setChecking] = useState(false);
  const [keywords, setKeywords] = useState<{ keyword: string }[]>([]);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    api.getPrKeywords(user?.token).then((list) => setKeywords(list.filter((k) => k.isActive)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetForm = () => {
    draft.clear();
    setF({ ...blank, newsDateTime: getNowDateTimeLocal() });
    setFiles(null);
    setMedia([]);
  };

  const pickFiles = async (list: FileList | null) => {
    setFiles(list);
    setMedia([]);
    if (!list?.length) return;
    setChecking(true);
    setMedia(await inspectFiles(list));
    setChecking(false);
  };

  /** คำค้นที่แอดมินตั้งไว้และพบในข่าวนี้ ดูสด ๆ ระหว่างพิมพ์ */
  const matched = keywords
    .map((k) => k.keyword)
    .filter((word) => `${f.title} ${f.content}`.toLowerCase().includes(word.toLowerCase()));

  const failing = media.filter((m) => !m.passed);

  const submit = async () => {
    if (!f.title.trim() || !f.newsType || !f.content.trim()) {
      Swal.fire('ข้อมูลไม่ครบ', 'กรุณากรอกหัวข้อ ประเภทข่าว และเนื้อหา', 'warning');
      return;
    }

    if (failing.length) {
      const r = await Swal.fire({
        title: 'สื่อบางไฟล์ต่ำกว่าเกณฑ์',
        html:
          `<div class="text-start small">มี <b>${failing.length}</b> ไฟล์ที่ความละเอียดต่ำกว่า ${MIN_SHORT_EDGE}p<br>` +
          failing.map((m) => `• ${m.name} — ${m.reason}`).join('<br>') +
          '<hr>ส่งได้ แต่ข่าวจะถูกจัดเข้า<b>คิวรอแอดมินพิจารณา</b>ก่อนเผยแพร่</div>',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'ส่งต่อไป',
        cancelButtonText: 'กลับไปเปลี่ยนไฟล์',
        confirmButtonColor: '#ffc107',
      });
      if (!r.isConfirmed) return;
    }

    loadingModal('กำลังส่งข่าว...');
    const payload = {
      ...f,
      source: 'internal',
      unitId: user?.unit,
      stationId: user?.station,
      actionBy: user?.username,
      // ส่งค่าที่วัดจากเบราว์เซอร์ไปด้วย backend ตรวจภาพซ้ำเองแล้วใช้ค่าของตัวเองแทน
      mediaMeta: media,
    };
    const res = await api.submitPrNews(payload, user?.token, await filesToBase64(files));

    if (res.status === 'success') {
      draft.clear();
      await Swal.fire({
        icon: 'success',
        title: 'ส่งข่าวเข้าคิวตรวจแล้ว',
        html:
          `<p>${res.message || ''}</p>` +
          (res.needsMediaReview
            ? '<p class="small text-warning">มีสื่อที่ต่ำกว่าเกณฑ์ ข่าวนี้จะรอแอดมินพิจารณาก่อน</p>'
            : '') +
          (res.matchedKeywords?.length
            ? `<p class="small">คำค้นที่ระบบตรวจพบ: ${res.matchedKeywords.join(', ')}</p>`
            : ''),
        confirmButtonColor: '#00f2ff',
      });
      onBack();
    } else {
      Swal.fire('ผิดพลาด', res.message || 'ส่งข่าวไม่สำเร็จ', 'error');
    }
  };

  return (
    <FormShell title="ส่งข่าวประชาสัมพันธ์" onBack={onBack} maxWidth={860}>
      <div className="glass-card w-100" style={{ borderTop: '4px solid #ffc107' }}>
        {draft.restored && <DraftNotice onClear={resetForm} />}
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">วันที่เวลาของข่าว</label>
            <div className="d-flex gap-2 align-items-stretch">
              <ThaiDateInput type="datetime-local" value={f.newsDateTime} onChange={(v) => set('newsDateTime', v)} />
              <button type="button" className="btn btn-outline-warning" onClick={() => set('newsDateTime', getNowDateTimeLocal())}>
                <i className="fa-solid fa-clock-rotate-left"></i>
              </button>
            </div>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">ประเภทข่าว *</label>
            <select className="form-select" value={f.newsType} onChange={(e) => set('newsType', e.target.value)}>
              <option value="">-- เลือกประเภท --</option>
              {NEWS_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div className="col-12">
            <label className="form-label small text-white-50">หัวข้อข่าว *</label>
            <input type="text" className="form-control border-warning" placeholder="พาดหัวข่าวสั้น ๆ" value={f.title} onChange={(e) => set('title', e.target.value)} />
          </div>
          <div className="col-12">
            <label className="form-label small text-white-50">เนื้อหาข่าว *</label>
            <textarea className="form-control" rows={6} placeholder="เล่าเหตุการณ์ตามลำดับ ใคร ทำอะไร ที่ไหน เมื่อไร ผลเป็นอย่างไร" value={f.content} onChange={(e) => set('content', e.target.value)} />
            <p className="text-white-50 mb-0" style={{ fontSize: '0.7rem' }}>
              * ระบบยังไม่ได้ต่อ AI เกลาข้อความ (FR-06) เนื้อหาที่พิมพ์จะถูกใช้ตามที่กรอก
            </p>
          </div>
          <div className="col-12 col-md-6">
            <label className="form-label small text-white-50">ผู้ส่งข่าว</label>
            <input type="text" className="form-control" value={f.reporterName} onChange={(e) => set('reporterName', e.target.value)} />
          </div>

          {matched.length > 0 && (
            <div className="col-12">
              <div className="alert py-2 mb-0 small" style={{ background: 'rgba(0,242,255,0.06)', border: '1px solid rgba(0,242,255,0.25)', color: '#e2e8f0', borderRadius: 8 }}>
                <i className="fa-solid fa-tags text-info"></i> คำค้นที่ระบบตรวจพบในข่าวนี้: <b>{matched.join(', ')}</b>
              </div>
            </div>
          )}

          <div className="col-12"><hr className="border-secondary" /><span className="badge bg-warning text-dark">ไฟล์สื่อ</span></div>
          <div className="col-12">
            <label className="form-label small text-white-50">แนบภาพ / วิดีโอ (เลือกได้หลายไฟล์)</label>
            <input type="file" className="form-control" multiple accept="image/*,video/*" onChange={(e) => pickFiles(e.target.files)} />
            <p className="text-white-50 mb-0" style={{ fontSize: '0.7rem' }}>
              * เกณฑ์คุณภาพ: ด้านสั้นของภาพ/วิดีโอไม่ต่ำกว่า {MIN_SHORT_EDGE} พิกเซล
              ไฟล์ที่ไม่ผ่านยังส่งได้ แต่ข่าวจะรอแอดมินพิจารณาก่อน
            </p>
          </div>

          {checking && (
            <div className="col-12 small text-info">
              <span className="spinner-border spinner-border-sm me-2"></span> กำลังตรวจความละเอียดไฟล์...
            </div>
          )}

          {media.length > 0 && (
            <div className="col-12">
              <div className="table-responsive">
                <table className="table table-sm table-hq align-middle mb-0">
                  <thead>
                    <tr><th>ไฟล์</th><th className="text-center">ความละเอียด</th><th className="text-center">ผลตรวจ</th></tr>
                  </thead>
                  <tbody>
                    {media.map((m) => (
                      <tr key={m.name}>
                        <td className="text-truncate" style={{ maxWidth: 260 }}>{m.name}</td>
                        <td className="text-center">{m.width && m.height ? `${m.width}x${m.height}` : '-'}</td>
                        <td className="text-center">
                          {m.passed ? (
                            <span className="text-success"><i className="fa-solid fa-circle-check"></i> ผ่านเกณฑ์</span>
                          ) : (
                            <span className="text-warning" title={m.reason}><i className="fa-solid fa-triangle-exclamation"></i> รอพิจารณา</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="col-12 mt-4">
            <button type="button" className="btn btn-warning w-100 py-2 fw-bold" style={{ borderRadius: 10 }} onClick={submit} disabled={checking}>
              <i className="fa-solid fa-paper-plane"></i> ส่งข่าวเข้าคิวตรวจ
            </button>
          </div>
        </div>
      </div>
    </FormShell>
  );
};

export default PrForm;
