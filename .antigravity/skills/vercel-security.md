# 6.5 Vercel & Secret Management Security
Skill นี้มุ่งเน้นการป้องกัน Supply Chain Attacks และการจัดการ Environment Variables อย่างปลอดภัยบน Vercel และ Cloud Platforms อื่นๆ

### 🚨 Incident Response Playbook (เมื่อเกิดเหตุการณ์ API Key หลุด)
หากสงสัยว่าระบบกลางถูกเจาะ ให้ดำเนินการตามลำดับขั้นตอนนี้ทันที (ห้ามข้ามขั้นตอน):
1. **Rotate Keys:** เข้าสู่ระบบของ API Providers (Gemini, OpenAI, Supabase, Stripe) เพื่อ Revoke Key เก่า และสร้าง Key ใหม่ทันที
2. **Update Environment Variables:** นำ Key ใหม่ไปใส่ใน Vercel
3. **Mark as Sensitive:** ⚠️ **บังคับ** ต้องติ๊กช่อง "Sensitive" ใน Vercel ทุกครั้ง เพื่อป้องกันการถูกอ่านค่ากลับ (Decrypt) หรือแสดงผลบน UI
4. **Force Redeploy:** ต้องทำการ Redeploy Production ใหม่ทั้งหมด (Clear Cache ด้วย) เพื่อให้ Build ใหม่ดึง Key ล่าสุดไปใช้งาน
5. **Audit Usage:** ตรวจสอบ Dashboard ของ API Providers ว่ามียอด Usage พุ่งผิดปกติก่อนหน้าการเปลี่ยน Key หรือไม่

### 🛡️ Secure Configuration Patterns
* **Client-side vs Server-side:** * ห้ามใส่ Secret Keys (เช่น Database URL, LLM API Keys, Payment Secrets) ไว้ในตัวแปรที่ขึ้นต้นด้วย `NEXT_PUBLIC_` หรือ `VITE_` เด็ดขาด เพราะมันจะถูกฝังลงในฝั่ง Client ที่ทุกคนเปิดดูได้
* **Environment Separation:** ต้องแยก Key สำหรับ Development, Preview และ Production ออกจากกันอย่างเด็ดขาด
* **API Restrictions:** หาก Provider รองรับ (เช่น Google Cloud, Stripe) ให้ตั้งค่าจำกัด Domain (HTTP Referrers) หรือจำกัด IP Address ที่อนุญาตให้เรียกใช้ API นั้นได้

### Code Pattern (Next.js App Router Security)
ตัวอย่างการดึง API Key มาใช้ฝั่ง Server เท่านั้น (ป้องกัน Key รั่วไหลไป Client)

```typescript
// app/api/generate/route.ts
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  // ✅ ถูกต้อง: ดึง Secret Key เฉพาะบน Server Edge/Node.js environment
  const apiKey = process.env.GEMINI_API_KEY;
  
  if (!apiKey) {
    return NextResponse.json({ error: "Server Configuration Error" }, { status: 500 });
  }

  try {
    const body = await request.json();
    // ดำเนินการเรียก API ปลายทางด้วย apiKey
    // ...
    return NextResponse.json({ success: true, data: result });
  } catch (error) {
    return NextResponse.json({ error: "Failed to process request" }, { status: 500 });
  }
}