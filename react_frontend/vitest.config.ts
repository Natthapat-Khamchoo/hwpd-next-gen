import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * ชุดทดสอบฝั่งหน้าเว็บ
 *
 * แยกไฟล์ config ออกจาก `vite.config.ts` เพราะ Tailwind plugin ไม่จำเป็นตอนรันเทส
 * และการโหลดมันเข้ามาทำให้เทสช้าลงโดยไม่ได้อะไรกลับมา
 *
 * ขอบเขตที่เลือกทดสอบ: ตรรกะที่ตัดสินใจแทนผู้ใช้และพังแบบเงียบ ๆ ได้ —
 * การเก็บร่างฟอร์ม เกณฑ์คุณภาพสื่อ การจัดกลุ่มข้อหา และข้อความที่คัดลอกไปส่ง LINE
 * ไม่ได้ไล่เทสทุก component เพราะการเรนเดอร์ตรงกับต้นฉบับ Apps Script ตรวจด้วยตา
 * และภาพหน้าจอง่ายกว่าและตรงจุดกว่า
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
