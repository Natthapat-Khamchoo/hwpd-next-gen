import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';

/**
 * ฟอร์มที่จำค่าที่กรอกไว้ได้เมื่อผู้ปฏิบัติกดย้อนกลับไปดูหน้าอื่นแล้วกลับมาทำต่อ
 *
 * แอปนี้ไม่มี react-router เปลี่ยนหน้าด้วย state ใน App.tsx ซึ่งทำให้ component ของ
 * ฟอร์มถูก unmount ทิ้งทั้งตัว state ที่กรอกไว้จึงหายหมดทุกครั้งที่กดกลับ ของเดิมที่เป็น
 * Apps Script ก็หายเหมือนกัน แต่เป็นเรื่องที่หน่วยขอให้แก้ (requirement ข้อ 12)
 *
 * ใช้ sessionStorage ไม่ใช่ localStorage เพราะร่างที่ยังไม่ส่งเป็นของรอบการทำงานนั้น
 * ปิดเบราว์เซอร์แล้วควรจบ ไม่ใช่ค้างข้ามวันจนเจ้าหน้าที่เผลอส่งข้อมูลของเมื่อวาน
 *
 * ข้อจำกัดที่ตั้งใจ: เก็บเฉพาะค่าที่แปลงเป็น JSON ได้ ไฟล์แนบ (`FileList`) แปลงไม่ได้
 * และไม่ควรเก็บอยู่แล้ว ทุกฟอร์มจึงแยก state ของไฟล์ไว้ต่างหากตามเดิม
 */

const PREFIX = 'hwpd:draft:';

/** ร่างที่เก่ากว่านี้ถือว่าเลิกใช้แล้ว กันไม่ให้ค่าเมื่อวานโผล่มาในรายงานวันนี้ */
export const DRAFT_TTL_MS = 24 * 60 * 60 * 1000;

/** หน่วงก่อนเขียนลง storage ไม่ให้เขียนทุกตัวอักษรที่พิมพ์ */
export const DRAFT_DEBOUNCE_MS = 500;

interface StoredDraft<T> {
  savedAt: number;
  values: T;
}

const storageKey = (formId: string, scope: string) => `${PREFIX}${scope}:${formId}`;

/** sessionStorage ใช้ไม่ได้ในโหมดส่วนตัวบางเบราว์เซอร์ ฟอร์มต้องยังทำงานได้ตามปกติ */
const safeStorage = (): Storage | null => {
  try {
    const probe = '__hwpd_probe__';
    window.sessionStorage.setItem(probe, '1');
    window.sessionStorage.removeItem(probe);
    return window.sessionStorage;
  } catch {
    return null;
  }
};

const readDraft = <T,>(key: string): T | null => {
  const store = safeStorage();
  if (!store) return null;
  try {
    const raw = store.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDraft<T>;
    if (!parsed || typeof parsed.savedAt !== 'number') {
      store.removeItem(key);
      return null;
    }
    if (Date.now() - parsed.savedAt > DRAFT_TTL_MS) {
      store.removeItem(key);
      return null;
    }
    return parsed.values;
  } catch {
    // ร่างที่พังอ่านไม่ออกดีกว่าทิ้งไว้ให้พังซ้ำทุกครั้งที่เปิดฟอร์ม
    store.removeItem(key);
    return null;
  }
};

/** ล้างร่างที่หมดอายุของทุกฟอร์มทิ้ง เรียกครั้งเดียวตอนเปิดฟอร์มไหนก็ได้ */
export const purgeExpiredDrafts = (): number => {
  const store = safeStorage();
  if (!store) return 0;

  const stale: string[] = [];
  for (let i = 0; i < store.length; i += 1) {
    const key = store.key(i);
    if (!key || !key.startsWith(PREFIX)) continue;
    try {
      const parsed = JSON.parse(store.getItem(key) || 'null') as StoredDraft<unknown> | null;
      if (!parsed || typeof parsed.savedAt !== 'number' || Date.now() - parsed.savedAt > DRAFT_TTL_MS) {
        stale.push(key);
      }
    } catch {
      stale.push(key);
    }
  }
  stale.forEach((key) => store.removeItem(key));
  return stale.length;
};

export interface DraftControls {
  /** ลบร่างทิ้ง เรียกทันทีที่บันทึกสำเร็จ ไม่งั้นค่าที่ส่งไปแล้วจะกลับมาอีกรอบ */
  clear: () => void;
  /** true เมื่อค่าเริ่มต้นมาจากร่างที่ค้างไว้ ไม่ใช่ค่าตั้งต้นของฟอร์ม */
  restored: boolean;
}

/**
 * ใช้แทน `useState` ในฟอร์ม คืนค่าชุดเดียวกันบวกตัวควบคุมร่าง
 *
 * ```tsx
 * const [f, setF, draft] = useFormDraft('checkpoint', { unitId: '', location: '' });
 * // ...บันทึกสำเร็จแล้ว
 * draft.clear();
 * ```
 *
 * `scope` แยกร่างของแต่ละบัญชี ไม่ให้ร่างของคนก่อนหน้าโผล่มาให้คนที่ล็อกอินต่อ
 * ซึ่งบนเครื่องที่ใช้ร่วมกันในหน่วยเป็นเรื่องที่เกิดได้จริง
 */
export function useFormDraft<T extends object>(
  formId: string,
  initialValues: T,
  scope = 'anon',
): [T, Dispatch<SetStateAction<T>>, DraftControls] {
  const key = storageKey(formId, scope);

  // อ่านร่างครั้งเดียวตอน mount ถ้าอ่านทุก render ค่าที่ผู้ใช้เพิ่งพิมพ์จะถูกทับ
  const [initial] = useState(() => {
    purgeExpiredDrafts();
    const saved = readDraft<T>(key);
    if (!saved) return { values: initialValues, restored: false };

    // ฟอร์มที่เก็บเป็น array (รายชื่อชุดจับกุม ผู้ต้องหา ฯลฯ) ต้องใช้ค่าที่บันทึกไว้ตรง ๆ
    // การ spread array เข้ากับ array ได้ object ที่มีคีย์เป็นตัวเลข ซึ่งพัง `.map()` ทั้งฟอร์ม
    // ส่วน object ธรรมดา merge ทับค่าตั้งต้น เผื่อฟอร์มเพิ่มฟิลด์ใหม่หลังจากมีร่างค้างอยู่
    const merged = Array.isArray(initialValues) || Array.isArray(saved)
      ? saved
      : ({ ...initialValues, ...saved } as T);

    return { values: merged, restored: true };
  });

  const [values, setValues] = useState<T>(initial.values);
  const [restored, setRestored] = useState(initial.restored);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // ค่าตั้งต้นตอน mount ใช้เทียบว่าฟอร์มยังว่างอยู่หรือเปล่า จับไว้ครั้งเดียวเพราะ
  // object ที่ฟอร์มส่งเข้ามาถูกสร้างใหม่ทุก render
  const pristine = useRef(JSON.stringify(initialValues));

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);

    const serialized = JSON.stringify(values);
    // ฟอร์มที่ยังไม่มีใครกรอกอะไรไม่ต้องเก็บร่าง ไม่งั้นหลังบันทึกสำเร็จแล้วฟอร์มรีเซ็ต
    // ตัวเอง จะได้ร่างเปล่าค้างไว้ แล้วรอบหน้าจะขึ้นว่า "กู้ร่างคืนแล้ว" ทั้งที่ไม่มีอะไรกู้
    if (serialized === pristine.current) return undefined;

    timer.current = setTimeout(() => {
      const store = safeStorage();
      if (!store) return;
      try {
        store.setItem(key, JSON.stringify({ savedAt: Date.now(), values } as StoredDraft<T>));
      } catch {
        // storage เต็มหรือถูกปิด ปล่อยผ่าน ฟอร์มยังกรอกและส่งได้ตามปกติ
      }
    }, DRAFT_DEBOUNCE_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [key, values]);

  const clear = useCallback(() => {
    // ยกเลิก debounce ที่ตั้งค้างไว้ ไม่งั้นค่าที่เพิ่งส่งไปจะถูกเขียนกลับลงไปหลังลบแล้ว
    if (timer.current) clearTimeout(timer.current);
    setRestored(false);
    const store = safeStorage();
    if (store) store.removeItem(key);
  }, [key]);

  return [values, setValues, { clear, restored }];
}
