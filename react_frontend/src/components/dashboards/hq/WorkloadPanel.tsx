import React from 'react';
import { ReactApexChart } from '../chartHelpers';

/**
 * ภาระงานต่อกำลังพล (พอร์ตจาก getExecutiveDashboardData)
 *
 * ตัวเลขที่ผู้กำกับการต้องใช้ตัดสินใจคือ "ภารกิจเฉลี่ยต่อคน" ไม่ใช่ยอดดิบ สถานีที่ทำ
 * งานได้เท่ากันแต่มีคนครึ่งเดียวคือสถานีที่กำลังรับภาระหนักกว่า ซึ่งดูจากกราฟแท่ง
 * ยอดผลงานอย่างเดียวไม่มีทางเห็น
 */

interface Props {
  categories: string[];
  staff: number[];
  ratio: number[];
  workload: Record<string, number[]>;
}

const mixedOptions = (categories: string[]): ApexCharts.ApexOptions => ({
  chart: { height: 340, toolbar: { show: false }, background: 'transparent' },
  theme: { mode: 'dark' },
  colors: ['#0dcaf0', '#facc15'],
  stroke: { width: [0, 3], curve: 'smooth' },
  plotOptions: { bar: { borderRadius: 4, columnWidth: '50%' } },
  dataLabels: { enabled: false },
  xaxis: { categories, labels: { style: { colors: '#8b949e' } } },
  yaxis: [
    { title: { text: 'กำลังพลปฏิบัติจริง (นาย)', style: { color: '#0dcaf0' } }, labels: { style: { colors: '#8b949e' } } },
    { opposite: true, title: { text: 'ภารกิจเฉลี่ยต่อคน', style: { color: '#facc15' } }, labels: { style: { colors: '#8b949e' } } },
  ],
  legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#fff' } },
  grid: { borderColor: '#30363d', strokeDashArray: 4 },
  tooltip: { theme: 'dark', shared: true, intersect: false },
});

export const WorkloadPanel: React.FC<Props> = ({ categories, staff, ratio, workload }) => {
  // สถานีที่ภาระต่อคนสูงสุด คือบรรทัดเดียวที่ผู้กำกับการต้องอ่านจากหน้านี้
  const peak = ratio.reduce((best, value, i) => (value > ratio[best] ? i : best), 0);

  return (
    <div className="row g-4 mb-4">
      <div className="col-12 col-lg-8">
        <div className="glass-card h-100">
          <h5 className="text-white mb-1"><i className="fa-solid fa-scale-unbalanced text-warning"></i> ภาระงานเทียบกำลังพล</h5>
          <p className="small text-white-50 mb-3">แท่ง = กำลังพลที่ปฏิบัติจริง (หักไปช่วยราชการ บวกที่มาช่วย) · เส้น = ภารกิจเฉลี่ยต่อคน</p>
          <ReactApexChart
            type="line"
            height={340}
            options={mixedOptions(categories)}
            series={[
              { name: 'กำลังพลปฏิบัติจริง', type: 'column', data: staff },
              { name: 'ภารกิจเฉลี่ยต่อคน', type: 'line', data: ratio },
            ]}
          />
        </div>
      </div>

      <div className="col-12 col-lg-4">
        <div className="glass-card h-100">
          <h5 className="text-white mb-3"><i className="fa-solid fa-ranking-star text-info"></i> สรุปรายสถานี</h5>
          {!!categories.length && (
            <div className="alert alert-warning py-2 small">
              ภาระต่อคนสูงสุด: <strong>{categories[peak]}</strong> ({ratio[peak]} ภารกิจ/คน จากกำลังพล {staff[peak]} นาย)
            </div>
          )}
          <div className="table-responsive" style={{ maxHeight: 250, overflowY: 'auto' }}>
            <table className="table table-sc table-bordered text-center align-middle small mb-0">
              <thead><tr><th className="text-start">สถานี</th><th>กำลังพล</th><th>งานรวม</th><th>งาน/คน</th></tr></thead>
              <tbody>
                {categories.map((name, i) => {
                  const total = Object.values(workload).reduce((sum, series) => sum + (series[i] || 0), 0);
                  return (
                    <tr key={name}>
                      <td className="text-start text-white">{name}</td>
                      <td>{staff[i]}</td>
                      <td>{total}</td>
                      <td className={i === peak ? 'text-warning fw-bold' : ''}>{ratio[i]}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
