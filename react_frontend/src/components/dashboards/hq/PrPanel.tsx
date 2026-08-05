import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { copyTextToClipboard } from '../../../utils/formHelpers';
import { recentStart, today } from './panelHelpers';
import Swal from 'sweetalert2';

/**
 * งานประชาสัมพันธ์ฝั่งแอดมิน (requirement ข้อ 13)
 *
 *   FR-04     ตารางรวมข่าวทุกแหล่ง พร้อม search/filter และส่งออก Excel
 *   FR-07/08  ประกอบชิ้นงาน PR ตามเทมเพลต แล้วสร้างลิงก์สาธารณะแบบอ่านอย่างเดียว
 *   FR-09     อนุมัติ/ปฏิเสธข่าว และจัดการคำค้น — เฉพาะแอดมิน
 *   FR-10     รายงานข่าวค้างอนุมัติแยกตามสังกัด
 *
 * การปฏิเสธข่าวใช้ soft delete ตาม FR-05 แถวยังอยู่ในชีตครบ ไม่มีปุ่มไหนในหน้านี้
 * ที่ลบข้อมูลออกจริง
 */

interface NewsItem {
  recordId: string;
  status: string;
  timestamp: string;
  date: string;
  title: string;
  newsType: string;
  source: string;
  content: string;
  matchedKeywords: string[];
  reporter: string;
  unit: string;
  needsMediaReview: boolean;
  reviewNote: string;
  attachments: string;
  shareUrl?: string;
  shareFileId?: string;
  shareTemplate?: string;
  sharedAt?: string;
}

interface PendingGroup {
  unit: string;
  station: string;
  total: number;
  needsMediaReview: number;
  oldestDays: number;
  items: (NewsItem & { waitingDays: number; bucket: string })[];
}

interface PendingReport {
  groups: PendingGroup[];
  totals: { pending: number; units: number; needsMediaReview: number; oldestDays: number };
  aging: { key: string; label: string; count: number }[];
}

/**
 * สีของช่วงอายุที่ค้าง — มีตัวเลขวันกำกับทุกที่ที่ใช้สีนี้
 * สีบอกความเร่งด่วนได้เร็วกว่าตัวเลข แต่ใช้สีอย่างเดียวไม่ได้ คนตาบอดสีจะอ่านไม่ออก
 */
const AGING_CLASS: Record<string, string> = {
  today: 'text-info',
  d1_3: 'text-white',
  d4_7: 'text-warning',
  over7: 'text-danger',
};

/**
 * หนีอักขระ HTML ก่อนยัดข้อความของผู้ใช้ลงใน `html:` ของ SweetAlert
 *
 * หัวข้อข่าวมาจากช่องกรอกอิสระ และ `sanitize_form_data` ฝั่ง backend กันแค่ formula
 * injection ของ Sheets ไม่ได้กัน markup ปล่อยเข้า `html:` ตรง ๆ คือช่องให้รันสคริปต์
 * ในหน้าแอดมิน ซึ่งเป็นหน้าที่มีสิทธิ์อนุมัติและสร้างลิงก์สาธารณะพอดี
 */
const esc = (text: string) =>
  String(text ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string,
  );

const SOURCE_LABELS: Record<string, string> = {
  internal: 'เจ้าหน้าที่ในหน่วย',
  cib: 'CIB',
  hwpd: 'HWPD',
};

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  Pending: { label: 'รออนุมัติ', cls: 'bg-warning text-dark' },
  Approved: { label: 'อนุมัติแล้ว', cls: 'bg-success' },
  Canceled: { label: 'ปฏิเสธ', cls: 'bg-danger' },
};

/**
 * รายงานข่าวค้างอนุมัติแยกตามสังกัด (FR-10)
 *
 * เรียงหน่วยที่มีใบค้างนานที่สุดขึ้นก่อน ไม่ใช่หน่วยที่ค้างเยอะที่สุด คนเปิดรายงานนี้
 * เปิดเพื่อหาว่าต้องไปตามใคร ใบที่ค้างมาเจ็ดวันสำคัญกว่ายี่สิบใบที่เพิ่งส่งเมื่อเช้า
 */
const PendingReportView: React.FC<{
  report: PendingReport | null;
  busy: boolean;
  start: string;
  end: string;
  error: string;
  openGroup: string;
  onRange: (start: string, end: string) => void;
  onRefresh: () => void;
  onToggleGroup: (unit: string) => void;
  onOpenNews: (item: NewsItem) => void;
}> = ({ report, busy, start, end, error, openGroup, onRange, onRefresh, onToggleGroup, onOpenNews }) => (
  <>
    <div className="glass-card mb-3">
      <div className="row g-2 align-items-end">
        <div className="col-6 col-md-3">
          <label className="form-label small text-white-50 mb-1" htmlFor="pr-report-start">ตั้งแต่วันที่</label>
          <input id="pr-report-start" type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                 value={start} onChange={(e) => onRange(e.target.value, end)} />
        </div>
        <div className="col-6 col-md-3">
          <label className="form-label small text-white-50 mb-1" htmlFor="pr-report-end">ถึงวันที่</label>
          <input id="pr-report-end" type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                 value={end} onChange={(e) => onRange(start, e.target.value)} />
        </div>
        <div className="col-12 col-md-3">
          <button className="btn btn-info btn-sm w-100 fw-bold" onClick={onRefresh} disabled={busy}>
            {busy ? 'กำลังรวบรวม...' : 'ดูข่าวค้างอนุมัติ'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-warning py-2 mt-3 mb-0 small">{error}</div>}

      {report && (
        <div className="d-flex flex-wrap gap-3 mt-3 align-items-center small">
          <span className="text-white">
            ค้างทั้งหมด <b className="text-warning">{report.totals.pending}</b> ใบ
            จาก <b>{report.totals.units}</b> สังกัด
          </span>
          {!!report.totals.needsMediaReview && (
            <span className="text-warning">
              <i className="fa-solid fa-triangle-exclamation"></i> ค้างตรวจสื่อ {report.totals.needsMediaReview} ใบ
            </span>
          )}
          <span className="ms-auto d-flex flex-wrap gap-2">
            {report.aging.map((bucket) => (
              <span key={bucket.key} className={`badge bg-dark border ${AGING_CLASS[bucket.key] || 'text-white'}`}>
                {bucket.label} {bucket.count}
              </span>
            ))}
          </span>
        </div>
      )}
    </div>

    <div className="glass-card">
      {busy && <div className="text-center py-4 text-white-50">กำลังรวบรวม...</div>}

      {!busy && report && !report.groups.length && (
        <div className="text-center py-4 text-white-50">
          <i className="fa-solid fa-circle-check text-success"></i> ไม่มีข่าวค้างอนุมัติในช่วงวันที่ที่เลือก
        </div>
      )}

      {!busy && report?.groups.map((group) => (
        <div key={group.unit} className="mb-2">
          <button className="btn w-100 text-start d-flex flex-wrap align-items-center gap-2 py-2"
                  style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)' }}
                  onClick={() => onToggleGroup(group.unit)}
                  aria-expanded={openGroup === group.unit}>
            <i className={`fa-solid fa-chevron-${openGroup === group.unit ? 'down' : 'right'} text-white-50`}></i>
            <span className="fw-bold text-white">{group.unit}</span>
            <span className="badge bg-warning text-dark">ค้าง {group.total} ใบ</span>
            <span className={`small ${AGING_CLASS[group.oldestDays > 7 ? 'over7' : group.oldestDays > 3 ? 'd4_7' : 'd1_3']}`}>
              นานสุด {group.oldestDays} วัน
            </span>
            {!!group.needsMediaReview && (
              <span className="small text-warning">
                <i className="fa-solid fa-triangle-exclamation"></i> ค้างตรวจสื่อ {group.needsMediaReview}
              </span>
            )}
          </button>

          {openGroup === group.unit && (
            <div className="table-responsive">
              <table className="table table-hq table-bordered align-middle small mb-0">
                <thead>
                  <tr>
                    <th style={{ minWidth: 220 }}>หัวข้อข่าว</th>
                    <th className="text-center">วันที่ส่ง</th>
                    <th className="text-center">ค้างมาแล้ว</th>
                    <th className="text-center">จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  {group.items.map((item) => (
                    <tr key={item.recordId}>
                      <td>
                        <div className="fw-bold">{item.title}</div>
                        <div className="text-white-50" style={{ fontSize: '.75rem' }}>
                          {item.newsType} · {item.reporter}
                        </div>
                      </td>
                      <td className="text-center">{item.date}</td>
                      <td className={`text-center fw-bold ${AGING_CLASS[item.bucket] || 'text-white'}`}>
                        {item.waitingDays} วัน
                      </td>
                      <td className="text-center">
                        <button className="btn btn-sm btn-outline-info" onClick={() => onOpenNews(item)}>
                          <i className="fa-solid fa-file-magnifying-glass"></i> ตรวจ
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  </>
);

export const PrPanel: React.FC<{ station: string; canDecide: boolean }> = ({ station, canDecide }) => {
  const { user } = useAuth();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    start: recentStart(),
    end: today(),
    source: '',
    status: '',
    keyword: '',
  });
  const [needsReview, setNeedsReview] = useState(false);
  const [viewing, setViewing] = useState<NewsItem | null>(null);
  const [viewMedia, setViewMedia] = useState<any[] | null>(null);
  const [keywords, setKeywords] = useState<{ keyword: string; category: string; isActive: boolean }[]>([]);
  const [showKeywords, setShowKeywords] = useState(false);

  const [tab, setTab] = useState<'news' | 'pending'>('news');
  const [report, setReport] = useState<PendingReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [openGroup, setOpenGroup] = useState('');

  const [templates, setTemplates] = useState<{ key: string; label: string }[]>([]);
  const [template, setTemplate] = useState('press');
  const [draft, setDraft] = useState('');
  const [shareBusy, setShareBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    setError('');
    const res = await api.listPrNews(
      { station, ...filters, needsReview: needsReview ? 'true' : '' },
      user?.token,
    );
    setBusy(false);
    if (res.status !== 'success') {
      setError(res.message || 'ดึงรายการข่าวไม่สำเร็จ');
      return;
    }
    setItems(res.data.items || []);
    setSummary(res.data.summary || null);
  };

  /** FR-10 — ข่าวค้างอนุมัติแยกตามสังกัด ใช้ช่วงวันที่เดียวกับตารางข่าว */
  const loadReport = async () => {
    setReportBusy(true);
    setError('');
    const res = await api.prPendingReport(
      { station, start: filters.start, end: filters.end },
      user?.token,
    );
    setReportBusy(false);
    if (res.status !== 'success') {
      setError(res.message || 'ดึงรายงานข่าวค้างอนุมัติไม่สำเร็จ');
      return;
    }
    setReport(res.data);
  };

  useEffect(() => {
    load();
    api.getPrKeywords(user?.token).then(setKeywords);
    api.getPrTemplates(user?.token).then((list) => {
      setTemplates(list);
      if (list.length) setTemplate((current) => (list.some((t) => t.key === current) ? current : list[0].key));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (tab === 'pending' && !report) loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const openNews = async (item: NewsItem) => {
    setViewing(item);
    setViewMedia(null);
    setDraft('');
    if (item.shareTemplate) setTemplate(item.shareTemplate);
    const res = await api.prNewsMedia(item.recordId, station, user?.token);
    setViewMedia(res.status === 'success' ? res.data : []);
  };

  /** FR-07 — ประกอบชิ้นงานเพื่อให้อ่านก่อน ยังไม่แตะ Drive และยังไม่มีลิงก์ */
  const composeDraft = async () => {
    if (!viewing) return;
    setShareBusy(true);
    const res = await api.composePrNews({ recordId: viewing.recordId, station, template }, user?.token);
    setShareBusy(false);
    if (res.status !== 'success') {
      Swal.fire('ประกอบชิ้นงานไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    setDraft(res.data.content || '');
  };

  const copyDraft = async () => {
    const ok = await copyTextToClipboard(draft);
    Swal.fire({
      icon: ok ? 'success' : 'error',
      title: ok ? 'คัดลอกข้อความแล้ว' : 'คัดลอกไม่สำเร็จ',
      text: ok ? '' : 'เบราว์เซอร์ไม่อนุญาตให้เข้าถึงคลิปบอร์ด กรุณาเลือกข้อความแล้วคัดลอกเอง',
      timer: ok ? 1400 : undefined,
      showConfirmButton: !ok,
    });
  };

  /** FR-08 — อัปชิ้นงานขึ้น Drive แล้วเปิดให้ทุกคนที่มีลิงก์ "อ่าน" ได้ */
  const share = async () => {
    if (!viewing) return;
    const label = templates.find((t) => t.key === template)?.label || template;
    const confirmed = await Swal.fire({
      title: 'สร้างลิงก์สาธารณะ',
      html:
        `ชิ้นงานแบบ <b>${esc(label)}</b> ของข่าว "<b>${esc(viewing.title)}</b>"<br>` +
        '<span class="small text-muted">ลิงก์นี้เปิดได้โดยไม่ต้องล็อกอิน แต่แก้ไขไม่ได้ ' +
        'และถอนคืนได้ตลอดเวลา</span>' +
        (viewing.shareUrl ? '<br><span class="small text-danger">ลิงก์เดิมของข่าวใบนี้จะถูกถอนอัตโนมัติ</span>' : ''),
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'สร้างลิงก์',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#0ea5e9',
    });
    if (!confirmed.isConfirmed) return;

    setShareBusy(true);
    const res = await api.sharePrNews({ recordId: viewing.recordId, station, template }, user?.token);
    setShareBusy(false);
    if (res.status !== 'success') {
      Swal.fire('สร้างลิงก์ไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    setDraft(res.data.content || '');
    setViewing({
      ...viewing,
      shareUrl: res.data.shareUrl,
      shareFileId: res.data.shareFileId,
      shareTemplate: res.data.template,
      sharedAt: res.data.sharedAt,
    });
    Swal.fire('สร้างลิงก์แล้ว', res.message || '', 'success');
    load();
  };

  const revokeShare = async () => {
    if (!viewing) return;
    const confirmed = await Swal.fire({
      title: 'ถอนลิงก์สาธารณะ',
      text: 'ลิงก์ที่แจกออกไปแล้วจะเปิดไม่ได้อีก ตัวไฟล์ยังอยู่บน Drive ให้ตามย้อนได้',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'ถอนลิงก์',
      cancelButtonText: 'ยกเลิก',
      confirmButtonColor: '#ef4444',
    });
    if (!confirmed.isConfirmed) return;

    setShareBusy(true);
    const res = await api.revokePrShare({ recordId: viewing.recordId, station }, user?.token);
    setShareBusy(false);
    if (res.status !== 'success') {
      Swal.fire('ถอนลิงก์ไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    setViewing({ ...viewing, shareUrl: '', shareFileId: '', sharedAt: '' });
    Swal.fire('ถอนแล้ว', res.message || '', 'success');
    load();
  };

  const decide = async (item: NewsItem, approve: boolean) => {
    let note = '';
    if (!approve) {
      const r = await Swal.fire({
        title: 'เหตุผลที่ปฏิเสธข่าวนี้',
        input: 'text',
        inputPlaceholder: 'เช่น ภาพความละเอียดต่ำเกินไป / เนื้อหาซ้ำกับข่าวเดิม',
        showCancelButton: true,
        confirmButtonText: 'ปฏิเสธข่าว',
        cancelButtonText: 'ยกเลิก',
        confirmButtonColor: '#ef4444',
      });
      if (!r.isConfirmed || !r.value) return;
      note = r.value;
    } else {
      const r = await Swal.fire({
        title: 'ยืนยันอนุมัติข่าว',
        html: `<b>${esc(item.title)}</b><br><span class="small text-muted">อนุมัติแล้วจะพร้อมนำไปเผยแพร่</span>`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'อนุมัติ',
        cancelButtonText: 'ยกเลิก',
        confirmButtonColor: '#10b981',
      });
      if (!r.isConfirmed) return;
    }

    const res = await api.decidePrNews({ recordId: item.recordId, station, approve, note }, user?.token);
    if (res.status !== 'success') {
      Swal.fire('ไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    setViewing(null);
    Swal.fire('เรียบร้อย', res.message || '', 'success');
    load();
    // ข่าวที่เพิ่งตัดสินไปแล้วต้องหลุดจากรายงานค้างอนุมัติทันที ไม่ใช่รอกดรีเฟรชเอง
    if (report) loadReport();
  };

  const addKeyword = async () => {
    const r = await Swal.fire({
      title: 'เพิ่มคำค้นสำหรับกรองข่าว',
      input: 'text',
      inputPlaceholder: 'เช่น ยาเสพติด, Scammer',
      showCancelButton: true,
      confirmButtonText: 'เพิ่ม',
      cancelButtonText: 'ยกเลิก',
    });
    if (!r.isConfirmed || !r.value) return;
    const res = await api.savePrKeyword({ keyword: r.value }, user?.token);
    if (res.status !== 'success') {
      Swal.fire('ไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    api.getPrKeywords(user?.token).then(setKeywords);
    Swal.fire('เพิ่มแล้ว', res.message || '', 'success');
  };

  /** ส่งออกเป็น CSV ที่ Excel เปิดได้ — BOM นำหน้าเพื่อให้ภาษาไทยไม่กลายเป็นขยะ */
  const exportCsv = () => {
    const header = ['รหัสข่าว', 'สถานะ', 'วันที่', 'หัวข้อข่าว', 'ประเภท', 'แหล่งที่มา', 'ผู้ส่ง', 'หน่วย', 'คำค้นที่พบ', 'ค้างตรวจสื่อ'];
    const rows = items.map((i) => [
      i.recordId, STATUS_BADGE[i.status]?.label || i.status, i.date, i.title,
      i.newsType, SOURCE_LABELS[i.source] || i.source, i.reporter, i.unit,
      i.matchedKeywords.join(' | '), i.needsMediaReview ? 'ใช่' : '',
    ]);
    const csv = [header, ...rows]
      .map((r) => r.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `PR_News_${today()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <ul className="nav nav-pills mb-3 flex-wrap gap-1">
        <li className="nav-item">
          <button className={`nav-link ${tab === 'news' ? 'active' : ''}`} onClick={() => setTab('news')}>
            <i className="fa-solid fa-newspaper"></i> ตารางรวมข่าว
          </button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${tab === 'pending' ? 'active' : ''}`} onClick={() => setTab('pending')}>
            <i className="fa-solid fa-hourglass-half"></i> ค้างอนุมัติแยกตามสังกัด
            {!!report?.totals.pending && (
              <span className="badge bg-warning text-dark ms-2">{report.totals.pending}</span>
            )}
          </button>
        </li>
      </ul>

      {tab === 'pending' && (
        <PendingReportView
          report={report}
          busy={reportBusy}
          start={filters.start}
          end={filters.end}
          error={error}
          openGroup={openGroup}
          onRange={(start, end) => setFilters({ ...filters, start, end })}
          onRefresh={loadReport}
          onToggleGroup={(unit) => setOpenGroup((current) => (current === unit ? '' : unit))}
          onOpenNews={openNews}
        />
      )}

      {tab === 'news' && (
      <>
      <div className="glass-card mb-3">
        <div className="row g-2 align-items-end">
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">ตั้งแต่วันที่</label>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                   value={filters.start} onChange={(e) => setFilters({ ...filters, start: e.target.value })} />
          </div>
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">ถึงวันที่</label>
            <input type="date" className="form-control form-control-sm bg-dark text-white border-secondary"
                   value={filters.end} onChange={(e) => setFilters({ ...filters, end: e.target.value })} />
          </div>
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">แหล่งที่มา</label>
            <select className="form-select form-select-sm" value={filters.source}
                    onChange={(e) => setFilters({ ...filters, source: e.target.value })}>
              <option value="">— ทุกแหล่ง —</option>
              {Object.entries(SOURCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="col-6 col-md-2">
            <label className="form-label small text-white-50 mb-1">สถานะ</label>
            <select className="form-select form-select-sm" value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">— ทุกสถานะ —</option>
              {Object.entries(STATUS_BADGE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div className="col-12 col-md-2">
            <label className="form-label small text-white-50 mb-1">ค้นหา</label>
            <input className="form-control form-control-sm" placeholder="หัวข้อ / เนื้อหา / ผู้ส่ง"
                   value={filters.keyword} onChange={(e) => setFilters({ ...filters, keyword: e.target.value })} />
          </div>
          <div className="col-12 col-md-2">
            <button className="btn btn-info btn-sm w-100 fw-bold" onClick={load} disabled={busy}>
              {busy ? 'กำลังค้น...' : 'ค้นหาข่าว'}
            </button>
          </div>
        </div>

        <div className="d-flex flex-wrap gap-2 mt-3 align-items-center">
          <button className={`btn btn-sm ${needsReview ? 'btn-warning' : 'btn-outline-warning'}`}
                  onClick={() => setNeedsReview((v) => !v)}>
            <i className="fa-solid fa-triangle-exclamation"></i> เฉพาะที่ค้างตรวจสื่อ
          </button>
          <button className="btn btn-sm btn-outline-info" onClick={() => setShowKeywords((v) => !v)}>
            <i className="fa-solid fa-tags"></i> คำค้น ({keywords.filter((k) => k.isActive).length})
          </button>
          {!!items.length && (
            <button className="btn btn-sm btn-outline-success" onClick={exportCsv}>
              <i className="fa-solid fa-file-excel"></i> ส่งออก Excel
            </button>
          )}
          {summary && (
            <span className="small text-white-50 ms-auto">
              ทั้งหมด {summary.total} · รออนุมัติ {summary.pending} · อนุมัติแล้ว {summary.approved} ·
              ค้างตรวจสื่อ {summary.needsMediaReview}
            </span>
          )}
        </div>

        {error && <div className="alert alert-warning py-2 mt-3 mb-0 small">{error}</div>}

        {showKeywords && (
          <div className="mt-3 p-3 rounded" style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="d-flex justify-content-between align-items-center mb-2">
              <span className="small text-info">คำค้นที่ใช้กรองข่าว (FR-02)</span>
              {canDecide && (
                <button className="btn btn-sm btn-outline-info" onClick={addKeyword}>
                  <i className="fa-solid fa-plus"></i> เพิ่มคำค้น
                </button>
              )}
            </div>
            {keywords.length ? (
              <div className="d-flex flex-wrap gap-2">
                {keywords.map((k) => (
                  <span key={k.keyword} className={`badge ${k.isActive ? 'bg-info text-dark' : 'bg-secondary'}`}>
                    {k.keyword}{k.category ? ` · ${k.category}` : ''}
                  </span>
                ))}
              </div>
            ) : (
              <div className="small text-white-50">ยังไม่มีคำค้น ข่าวทุกใบจะผ่านการกรองไปตามปกติ</div>
            )}
          </div>
        )}
      </div>

      <div className="glass-card">
        <div className="table-responsive">
          <table className="table table-hq table-bordered align-middle small mb-0">
            <thead>
              <tr>
                <th style={{ minWidth: 220 }}>หัวข้อข่าว</th>
                <th className="text-center">แหล่งที่มา</th>
                <th className="text-center">วันที่</th>
                <th className="text-center">สถานะ</th>
                <th className="text-center">จัดการ</th>
              </tr>
            </thead>
            <tbody>
              {busy && <tr><td colSpan={5} className="text-center py-4 text-white-50">กำลังโหลด...</td></tr>}
              {!busy && !items.length && (
                <tr><td colSpan={5} className="text-center py-4 text-white-50">ไม่มีข่าวตามเงื่อนไขที่เลือก</td></tr>
              )}
              {!busy && items.map((item) => (
                <tr key={item.recordId}>
                  <td>
                    <div className="fw-bold">{item.title}</div>
                    <div className="text-white-50" style={{ fontSize: '.75rem' }}>
                      {item.newsType} · {item.reporter}
                      {item.needsMediaReview && (
                        <span className="text-warning ms-2">
                          <i className="fa-solid fa-triangle-exclamation"></i> ค้างตรวจสื่อ
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="text-center">{SOURCE_LABELS[item.source] || item.source}</td>
                  <td className="text-center">{item.date}</td>
                  <td className="text-center">
                    <span className={`badge ${STATUS_BADGE[item.status]?.cls || 'bg-secondary'}`}>
                      {STATUS_BADGE[item.status]?.label || item.status}
                    </span>
                  </td>
                  <td className="text-center">
                    <button className="btn btn-sm btn-outline-info" onClick={() => openNews(item)}>
                      <i className="fa-solid fa-file-magnifying-glass"></i> ตรวจ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

      {viewing && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-start justify-content-center"
             style={{ background: 'rgba(0,0,0,.75)', zIndex: 2000, overflowY: 'auto', padding: '3vh 1rem' }}>
          <div className="glass-card p-4" style={{ maxWidth: 780, width: '100%' }}>
            <div className="d-flex justify-content-between align-items-start mb-3 gap-2">
              <div>
                <h5 className="text-white m-0">{viewing.title}</h5>
                <small className="text-white-50">
                  {viewing.recordId} · {SOURCE_LABELS[viewing.source] || viewing.source} · {viewing.timestamp}
                </small>
              </div>
              <button className="btn btn-sm btn-outline-light" onClick={() => setViewing(null)}>ปิด</button>
            </div>

            <pre className="text-white p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontFamily: 'Kanit', fontSize: '.9rem', background: 'rgba(0,0,0,.3)' }}>
              {viewing.content || '(ไม่มีเนื้อหา)'}
            </pre>

            {!!viewing.matchedKeywords.length && (
              <div className="small mb-3">
                <span className="text-white-50">คำค้นที่พบ:</span>{' '}
                {viewing.matchedKeywords.map((k) => <span key={k} className="badge bg-info text-dark me-1">{k}</span>)}
              </div>
            )}

            <div className="small text-white-50 mb-2"><i className="fa-solid fa-photo-film"></i> ไฟล์สื่อ</div>
            {viewMedia === null ? (
              <div className="small text-white-50">กำลังโหลด...</div>
            ) : viewMedia.length ? (
              <div className="table-responsive mb-3">
                <table className="table table-sm table-hq mb-0">
                  <tbody>
                    {viewMedia.map((m: any) => (
                      <tr key={m.recordId}>
                        <td className="text-truncate" style={{ maxWidth: 240 }}>{m.name}</td>
                        <td className="text-center">{m.width && m.height ? `${m.width}x${m.height}` : '-'}</td>
                        <td className="text-center">
                          {m.passed
                            ? <span className="text-success">ผ่านเกณฑ์</span>
                            : <span className="text-warning" title={m.reason}>ต่ำกว่าเกณฑ์</span>}
                        </td>
                        <td className="text-center text-white-50" style={{ fontSize: '.7rem' }}>{m.checkedBy}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="small text-warning mb-3">
                <i className="fa-solid fa-triangle-exclamation"></i> ข่าวนี้ไม่มีไฟล์สื่อแนบ
              </div>
            )}

            {viewing.attachments && viewing.attachments.startsWith('http') && (
              <a className="btn btn-sm btn-outline-info mb-3" href={viewing.attachments} target="_blank" rel="noreferrer">
                <i className="fa-solid fa-folder-open"></i> เปิดโฟลเดอร์ไฟล์แนบ
              </a>
            )}

            {canDecide && (
              <div className="mt-3 p-3 rounded" style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="small text-info mb-2">
                  <i className="fa-solid fa-bullhorn"></i> ชิ้นงานประชาสัมพันธ์ (FR-07/08)
                </div>

                <div className="row g-2 align-items-end">
                  <div className="col-12 col-md-5">
                    <label className="form-label small text-white-50 mb-1" htmlFor="pr-template">รูปแบบชิ้นงาน</label>
                    <select id="pr-template" className="form-select form-select-sm" value={template}
                            onChange={(e) => { setTemplate(e.target.value); setDraft(''); }}>
                      {templates.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
                    </select>
                  </div>
                  <div className="col-6 col-md-4">
                    <button className="btn btn-sm btn-outline-info w-100" onClick={composeDraft} disabled={shareBusy}>
                      <i className="fa-solid fa-wand-magic-sparkles"></i> {shareBusy ? 'กำลังทำ...' : 'ประกอบชิ้นงาน'}
                    </button>
                  </div>
                  <div className="col-6 col-md-3">
                    <button className="btn btn-sm btn-info w-100 fw-bold" onClick={share}
                            disabled={shareBusy || viewing.status !== 'Approved'}
                            title={viewing.status !== 'Approved' ? 'สร้างลิงก์สาธารณะได้เฉพาะข่าวที่อนุมัติแล้ว' : ''}>
                      <i className="fa-solid fa-link"></i> สร้างลิงก์
                    </button>
                  </div>
                </div>

                {viewing.status !== 'Approved' && (
                  <div className="small text-white-50 mt-2">
                    <i className="fa-solid fa-circle-info"></i> ดูตัวอย่างชิ้นงานได้เลย แต่ลิงก์สาธารณะสร้างได้
                    เฉพาะข่าวที่อนุมัติแล้ว
                  </div>
                )}

                {!!draft && (
                  <>
                    <textarea className="form-control form-control-sm mt-3" rows={10} readOnly value={draft}
                              aria-label="ตัวอย่างชิ้นงานประชาสัมพันธ์"
                              style={{ fontFamily: 'Kanit', fontSize: '.85rem' }} />
                    <button className="btn btn-sm btn-outline-light mt-2" onClick={copyDraft}>
                      <i className="fa-solid fa-copy"></i> คัดลอกข้อความ
                    </button>
                  </>
                )}

                {viewing.shareUrl ? (
                  <div className="mt-3 small">
                    <div className="text-success mb-1">
                      <i className="fa-solid fa-globe"></i> ลิงก์สาธารณะ (อ่านอย่างเดียว)
                      {viewing.sharedAt && <span className="text-white-50 ms-2">สร้างเมื่อ {viewing.sharedAt.slice(0, 16).replace('T', ' ')}</span>}
                    </div>
                    <div className="d-flex flex-wrap gap-2 align-items-center">
                      <a className="text-info text-truncate" style={{ maxWidth: 340 }} href={viewing.shareUrl}
                         target="_blank" rel="noreferrer">{viewing.shareUrl}</a>
                      <button className="btn btn-sm btn-outline-light" onClick={() => copyTextToClipboard(viewing.shareUrl || '')}
                              aria-label="คัดลอกลิงก์สาธารณะ">
                        <i className="fa-solid fa-copy"></i> คัดลอกลิงก์
                      </button>
                      <button className="btn btn-sm btn-outline-danger" onClick={revokeShare} disabled={shareBusy}>
                        <i className="fa-solid fa-link-slash"></i> ถอนลิงก์
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="small text-white-50 mt-3">
                    <i className="fa-solid fa-lock"></i> ยังไม่มีลิงก์สาธารณะของข่าวใบนี้
                  </div>
                )}
              </div>
            )}

            {canDecide && viewing.status === 'Pending' && (
              <div className="d-flex gap-2 mt-3">
                <button className="btn btn-success fw-bold flex-grow-1" onClick={() => decide(viewing, true)}>
                  <i className="fa-solid fa-check"></i> อนุมัติข่าวนี้
                </button>
                <button className="btn btn-outline-danger flex-grow-1" onClick={() => decide(viewing, false)}>
                  <i className="fa-solid fa-xmark"></i> ปฏิเสธ
                </button>
              </div>
            )}
            {!canDecide && (
              <div className="small text-white-50">
                <i className="fa-solid fa-lock"></i> เฉพาะแอดมินเท่านั้นที่อนุมัติหรือปฏิเสธข่าวได้ (FR-09)
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
