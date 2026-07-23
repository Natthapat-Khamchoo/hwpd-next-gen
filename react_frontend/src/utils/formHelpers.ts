import Swal from 'sweetalert2';

const THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];

/** Current local datetime as a value for <input type="datetime-local">. */
export const getNowDateTimeLocal = (): string => {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Current local date as a value for <input type="date">. */
export const getNowDateLocal = (): string => getNowDateTimeLocal().split('T')[0];

/** Thai-friendly date/time for the LINE preview box (พ.ศ. year). */
export const formatPreviewDate = (datetimeStr?: string): string => {
  if (!datetimeStr || typeof datetimeStr !== 'string') return '-';
  try {
    if (datetimeStr.includes('T')) {
      const [datePart, timePart] = datetimeStr.split('T');
      const [y, m, d] = datePart.split('-');
      const yy = (parseInt(y) + 543).toString().slice(-2);
      const mm = THAI_MONTHS[parseInt(m) - 1];
      const dd = parseInt(d).toString();
      const t = timePart.slice(0, 5).replace(':', '.');
      return `${dd} ${mm} ${yy} เวลา ${t} น.`;
    }
    const [y, m, d] = datetimeStr.split('-');
    const yy = (parseInt(y) + 543).toString().slice(-2);
    const mm = THAI_MONTHS[parseInt(m) - 1];
    const dd = parseInt(d).toString();
    return `${dd} ${mm} ${yy}`;
  } catch {
    return datetimeStr;
  }
};

/** Compute the station full name + province, mirroring getFrontendStationData(). */
export const getFrontendStationData = (stationId?: string, province = ''): { p: string; f: string } => {
  const strId = String(stationId || '51').trim();
  const divisionNum = strId.substring(0, 1);
  const stationNum = strId.substring(1);
  const fullName =
    stationNum === '0' ? `ฝอ.กก.${divisionNum} บก.ทล.` : `ส.ทล.${stationNum} กก.${divisionNum} บก.ทล.`;
  return { p: province, f: fullName };
};

/** Read a list of File objects as base64 data-URL payloads. */
export const filesToBase64 = (
  fileList: FileList | File[] | null,
): Promise<{ name: string; type: string; data: string }[]> => {
  if (!fileList) return Promise.resolve([]);
  const files = Array.from(fileList);
  return Promise.all(
    files.map(
      (f) =>
        new Promise<{ name: string; type: string; data: string }>((resolve) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve({ name: f.name, type: f.type, data: String(e.target?.result || '') });
          reader.readAsDataURL(f);
        }),
    ),
  );
};

const copyTextToClipboard = async (text: string): Promise<boolean> => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
};

const escapeHtml = (str: string): string =>
  String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

/**
 * Show the "ตรวจสอบข้อความก่อนส่ง LINE" confirmation modal.
 * Returns { confirmed, copied } — copied reflects the clipboard write done
 * during the genuine click (more reliable than copying later in async code).
 */
export const confirmLinePreview = async (
  previewText: string,
): Promise<{ confirmed: boolean; copied: boolean }> => {
  const result = await Swal.fire({
    title: 'ตรวจสอบข้อความก่อนส่ง LINE',
    html: `<pre class="line-preview">${escapeHtml(previewText)}</pre>`,
    icon: 'info',
    showCancelButton: true,
    confirmButtonColor: '#198754',
    cancelButtonColor: '#6c757d',
    confirmButtonText: '<i class="fa-solid fa-paper-plane"></i> ยืนยันข้อมูลถูกต้อง',
    cancelButtonText: 'กลับไปแก้ไข',
    width: '600px',
  });
  if (!result.isConfirmed) return { confirmed: false, copied: false };
  const copied = await copyTextToClipboard(previewText);
  return { confirmed: true, copied };
};

/** Success modal that offers the LINE text for the officer to paste into the group chat. */
export const showLineCopyResult = async (
  successMsg: string,
  lineText: string,
  alreadyCopied?: boolean,
): Promise<void> => {
  const copied = typeof alreadyCopied === 'boolean' ? alreadyCopied : await copyTextToClipboard(lineText);
  const r = await Swal.fire({
    title: 'บันทึกสำเร็จ!',
    html: `<p class="mb-2">${escapeHtml(successMsg)}</p>
      <p class="small ${copied ? 'text-success' : 'text-warning'} mb-2">${
        copied
          ? '<i class="fa-solid fa-check-circle"></i> คัดลอกข้อความเรียบร้อยแล้ว นำไปวางส่งในกลุ่ม LINE ได้เลย'
          : '<i class="fa-solid fa-triangle-exclamation"></i> คัดลอกอัตโนมัติไม่สำเร็จ กรุณากดปุ่มคัดลอกด้านล่าง'
      }</p>
      <pre class="line-preview">${escapeHtml(lineText)}</pre>`,
    icon: 'success',
    showCancelButton: true,
    confirmButtonColor: '#198754',
    confirmButtonText: 'เสร็จสิ้น',
    cancelButtonText: '<i class="fa-solid fa-copy"></i> คัดลอกอีกครั้ง',
    width: '600px',
  });
  if (r.dismiss === Swal.DismissReason.cancel) {
    const copiedAgain = await copyTextToClipboard(lineText);
    return showLineCopyResult(successMsg, lineText, copiedAgain);
  }
};

export const loadingModal = (title = 'กำลังบันทึกข้อมูล...') => {
  Swal.fire({ title, allowOutsideClick: false, didOpen: () => Swal.showLoading() });
};
