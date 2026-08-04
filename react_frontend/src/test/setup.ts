import { afterEach, beforeEach } from 'vitest';
import { cleanup } from '@testing-library/react';

/**
 * ล้างสถานะระหว่างเทสทุกตัว
 *
 * `sessionStorage` ต้องล้างด้วยเพราะ `useFormDraft` เก็บร่างไว้ที่นั่น ถ้าไม่ล้าง
 * เทสตัวถัดไปจะเห็นร่างของเทสก่อนหน้าแล้วผ่าน/ตกด้วยเหตุผลที่ไม่เกี่ยวกับตัวมันเอง
 * ซึ่งเป็นความล้มเหลวแบบที่หาสาเหตุยากที่สุด
 */
beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});
