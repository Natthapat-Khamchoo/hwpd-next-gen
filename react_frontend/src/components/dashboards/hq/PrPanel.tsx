import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { api } from '../../../services/api';
import { recentStart, today } from './panelHelpers';
import Swal from 'sweetalert2';

/**
 * งานประชาสัมพันธ์ฝั่งแอดมิน (requirement ข้อ 13)
 *
 *   FR-04  ตารางรวมข่าวทุกแหล่ง พร้อม search/filter และส่งออก Excel
 *   FR-09  อนุมัติ/ปฏิเสธข่าว และจัดการคำค้น — เฉพาะแอดมิน
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
}

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

  useEffect(() => {
    load();
    api.getPrKeywords(user?.token).then(setKeywords);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openNews = async (item: NewsItem) => {
    setViewing(item);
    setViewMedia(null);
    const res = await api.prNewsMedia(item.recordId, station, user?.token);
    setViewMedia(res.status === 'success' ? res.data : []);
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
        html: `<b>${item.title}</b><br><span class="small text-muted">อนุมัติแล้วจะพร้อมนำไปเผยแพร่</span>`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'อนุมัติ',
        cancelButtonText: 'ยกเลิก',
        confirmButtonColor: '#10b981',
      });
      if (!r.isConfirmed) return;
    }

    const res = await api.decidePrNews({ recordId: item.recordId, approve, note }, user?.token);
    if (res.status !== 'success') {
      Swal.fire('ไม่สำเร็จ', res.message || '', 'error');
      return;
    }
    setViewing(null);
    Swal.fire('เรียบร้อย', res.message || '', 'success');
    load();
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

            {canDecide && viewing.status === 'Pending' && (
              <div className="d-flex gap-2 mt-2">
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
