import Swal from 'sweetalert2';

/**
 * บันทึกพื้นที่หนึ่งของหน้าเป็นรูปภาพ (พอร์ตจาก exportCommanderDashboardToImage)
 *
 * ผู้กำกับการใช้แคปหน้า Dashboard ทั้งหน้าส่งเข้า LINE แทนการถ่ายจอทีละส่วน
 *
 * ปัญหาหลักคือ dashboard อยู่ในกล่องที่ scroll ได้ html2canvas จึงเห็นแค่ส่วนที่
 * แสดงอยู่ ของเดิมแก้ด้วยการปลดล็อกความสูงตั้งแต่ระดับ html ลงมาชั่วคราว แคป แล้วคืนค่า
 * ที่นี่ทำแบบเดียวกัน แต่เก็บ/คืนค่าใน finally เพื่อให้หน้าไม่ค้างเพี้ยนถ้าแคปล้มกลางคัน
 *
 * โหลด html2canvas แบบ dynamic import — เป็นไลบรารีก้อนใหญ่ที่ใช้ตอนกดปุ่มเท่านั้น
 * ไม่ควรถ่วงเวลาเปิดหน้าของทุกคน
 */

interface Options {
  /** พื้นที่ที่จะแคป — ปกติคือกล่องเนื้อหาที่ scroll ได้ */
  target: HTMLElement;
  filename: string;
  /** อีลิเมนต์ที่ต้องซ่อนระหว่างแคป เช่น ปุ่มเปิดเมนูบนมือถือ */
  hide?: (HTMLElement | null)[];
}

export const captureToImage = async ({ target, filename, hide = [] }: Options): Promise<void> => {
  Swal.fire({
    title: 'กำลังสร้างรูปภาพ...',
    text: 'ระบบกำลังขยายหน้าจอเพื่อเก็บภาพให้ครบทั้งหน้า',
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  const html = document.documentElement;
  const body = document.body;
  const saved = {
    html: html.style.cssText,
    body: body.style.cssText,
    target: target.style.cssText,
    scrollTop: target.scrollTop,
    hidden: hide.map((el) => el?.style.display ?? ''),
  };

  try {
    hide.forEach((el) => { if (el) el.style.display = 'none'; });

    // ปลดล็อกความสูงทุกชั้น ไม่งั้นได้ภาพแค่ส่วนที่มองเห็น
    html.style.height = 'auto';
    html.style.overflow = 'visible';
    body.style.height = 'auto';
    body.style.overflow = 'visible';
    target.style.height = 'auto';
    target.style.maxHeight = 'none';
    target.style.overflow = 'visible';
    window.scrollTo(0, 0);

    // รอให้ layout กับกราฟวาดใหม่เสร็จก่อนแคป ไม่งั้นได้ภาพกราฟเปล่า
    await new Promise((resolve) => setTimeout(resolve, 800));

    const { default: html2canvas } = await import('html2canvas');
    const canvas = await html2canvas(target, {
      scale: 2,
      backgroundColor: '#0d1117',
      useCORS: true,
      logging: false,
      width: target.scrollWidth,
      height: target.scrollHeight,
      windowWidth: target.scrollWidth,
      windowHeight: target.scrollHeight,
      scrollX: 0,
      scrollY: 0,
    });

    const link = document.createElement('a');
    link.download = `${filename}.jpg`;
    link.href = canvas.toDataURL('image/jpeg', 0.9);
    link.click();

    Swal.fire('สำเร็จ!', 'บันทึกรูปภาพเรียบร้อยแล้ว', 'success');
  } catch (error) {
    console.error('capture failed', error);
    Swal.fire('ผิดพลาด', 'สร้างรูปภาพไม่สำเร็จ กรุณาลองใหม่อีกครั้ง', 'error');
  } finally {
    // คืนค่าเสมอ ถึงจะแคปล้มก็ต้องไม่ทิ้งหน้าไว้ในสภาพที่ความสูงถูกปลดล็อก
    html.style.cssText = saved.html;
    body.style.cssText = saved.body;
    target.style.cssText = saved.target;
    target.scrollTop = saved.scrollTop;
    hide.forEach((el, i) => { if (el) el.style.display = saved.hidden[i]; });
  }
};
