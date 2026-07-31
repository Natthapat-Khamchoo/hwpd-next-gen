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
