import type { UserRole } from '../types';

/**
 * ใครเข้าเมนูการปฏิบัติงานได้บ้าง
 *
 * ของเดิม (index.html สาย showMainMenu) ซ่อน mainMenu ให้ทุก role แล้วเปิดกลับมา
 * เฉพาะสองทาง: switchToUserMode ใน admin_dashboard (สิบเวร/Station_Admin) กับปุ่ม
 * btnBackToAdmin ที่ hq_dashboard ตั้งไว้ (Division_Admin) ส่วน hq_admin_dashboard
 * กับ super_commander_dashboard ไม่มีทางกลับเมนูหลักเลยสักปุ่ม
 *
 * ไม่ใช่แค่เรื่องหน้าตา บัญชีระดับ บก. อยู่สถานี 00 ซึ่งไม่มีใน DB_ROUTER ทุกเมนู
 * ที่เขียนหรืออ่านฐานข้อมูลปฏิบัติการจึงตอบ 400 ว่า "กองกำกับการ 0 (สถานี 00) ยังไม่ได้
 * ตั้งค่าฐานข้อมูลปฏิบัติการ" การโชว์เมนูให้กดคือพาไปเจอ error ไม่ใช่พาไปทำงาน
 *
 * `PR_Officer` ไม่อยู่ในชุดนี้ด้วยเหตุผลที่ต่างออกไป — ไม่ใช่เพราะกดแล้วพัง แต่เพราะ
 * บัญชีนั้นเรียก endpoint นอกงาน PR ไม่ได้จริง ๆ (`PR_ONLY_ALLOWED_PREFIXES` ฝั่ง
 * backend) การซ่อนเมนูตรงนี้เป็นแค่การไม่พาไปกดของที่ยังไงก็ได้ 403
 */
const MAIN_MENU_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  'Unit_Staff',
  'สิบเวร',
  'Station_Admin',
  'Division_Admin',
  'Division_Commander',
]);

export const canUseMainMenu = (role?: UserRole): boolean =>
  MAIN_MENU_ROLES.has((role || 'Unit_Staff') as UserRole);

/**
 * หน้าแรกหลังล็อกอินของแต่ละบทบาท ตรงกับสาย showMainMenu ใน index.html เดิม
 *
 * อยู่ที่นี่แทนที่จะอยู่ใน App.tsx เพราะปุ่ม "กลับแผงควบคุม" ในเมนูผู้ปฏิบัติต้องใช้
 * ค่าเดียวกัน ก่อนหน้านี้ปุ่มนั้นฮาร์ดโค้ดไปหน้าสถานี ฝอ.กก. กดแล้วจึงไปผิดที่
 */
export const roleHome = (role?: UserRole): string => {
  switch (role) {
    case 'สิบเวร':
    case 'Station_Admin':
      return 'station_admin';
    case 'Division_Admin':
      return 'hq';
    case 'Division_Commander':
      return 'commander';
    case 'Super_Commander':
      return 'super_commander';
    case 'HQ_Admin':
      return 'hq_admin';
    case 'PR_Officer':
      return 'pr_center';
    default:
      return 'main';
  }
};
