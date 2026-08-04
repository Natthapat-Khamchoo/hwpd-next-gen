/**
 * ตรวจความละเอียดสื่อก่อนอัปโหลด (requirement ข้อ 13 — FR-02 / BR-01)
 *
 * ตรวจฝั่งเบราว์เซอร์เพื่อบอกผู้ใช้ทันทีว่าไฟล์ไหนจะติดคิวรอพิจารณา แทนที่จะให้
 * รออัปโหลดเสร็จแล้วค่อยรู้ **ค่าที่วัดจากที่นี่ไม่ใช่คำตอบสุดท้าย** ฝั่ง backend
 * ตรวจภาพซ้ำด้วย Pillow เสมอ เพราะค่าจากหน้าเว็บแก้ได้ด้วย DevTools
 */

/** ด้านสั้นต้องไม่ต่ำกว่าค่านี้ ต้องตรงกับ `pr_service.MIN_SHORT_EDGE` ฝั่ง backend */
export const MIN_SHORT_EDGE = 1080;

export interface MediaMeta {
  name: string;
  type: string;
  size: number;
  width: number;
  height: number;
  passed: boolean;
  reason: string;
}

/**
 * ผ่านเกณฑ์หรือไม่ วัดจาก **ด้านสั้น** ไม่ใช่ความสูง
 *
 * สื่อที่ถ่ายจากมือถือเป็นแนวตั้ง (1080x1920) การเช็คแค่ความสูงจะตกภาพแนวนอน
 * ที่ถูกต้อง (1920x1080) ส่วนการเช็คแค่ความกว้างจะตกภาพแนวตั้ง
 */
export const checkDimensions = (width: number, height: number): { passed: boolean; reason: string } => {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { passed: false, reason: 'อ่านขนาดไฟล์ไม่ได้ ต้องให้เจ้าหน้าที่ตรวจเอง' };
  }
  if (Math.min(width, height) < MIN_SHORT_EDGE) {
    return { passed: false, reason: `ความละเอียด ${width}x${height} ต่ำกว่าเกณฑ์ ${MIN_SHORT_EDGE}p` };
  }
  return { passed: true, reason: '' };
};

const readImageSize = (file: File): Promise<{ width: number; height: number }> =>
  new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
      URL.revokeObjectURL(url);
    };
    // ไฟล์ที่อ่านไม่ได้คืน 0x0 ซึ่ง checkDimensions จะตีเป็น "ไม่ผ่าน" ให้คนมาดู
    image.onerror = () => {
      resolve({ width: 0, height: 0 });
      URL.revokeObjectURL(url);
    };
    image.src = url;
  });

const readVideoSize = (file: File): Promise<{ width: number; height: number }> =>
  new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.onloadedmetadata = () => {
      resolve({ width: video.videoWidth, height: video.videoHeight });
      URL.revokeObjectURL(url);
    };
    video.onerror = () => {
      resolve({ width: 0, height: 0 });
      URL.revokeObjectURL(url);
    };
    video.src = url;
  });

/** อ่านขนาดของไฟล์เดียว ไฟล์ที่ไม่ใช่ภาพหรือวิดีโอคืน 0x0 */
export const readMediaSize = async (file: File): Promise<{ width: number; height: number }> => {
  if (file.type.startsWith('image/')) return readImageSize(file);
  if (file.type.startsWith('video/')) return readVideoSize(file);
  return { width: 0, height: 0 };
};

/** ตรวจทุกไฟล์ที่ผู้ใช้เลือก คืนผลตามลำดับเดิมเพื่อให้จับคู่กับ base64 ที่ส่งไปได้ */
export const inspectFiles = async (files: FileList | File[] | null): Promise<MediaMeta[]> => {
  if (!files) return [];
  const list = Array.from(files);
  return Promise.all(
    list.map(async (file) => {
      const { width, height } = await readMediaSize(file);
      const { passed, reason } = checkDimensions(width, height);
      return { name: file.name, type: file.type, size: file.size, width, height, passed, reason };
    }),
  );
};
