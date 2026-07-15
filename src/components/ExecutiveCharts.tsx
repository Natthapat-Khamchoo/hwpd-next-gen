'use client';

import React from 'react';
import dynamic from 'next/dynamic';

const Chart = dynamic(() => import('react-apexcharts'), { ssr: false });

interface StationStat {
  stationId: string;
  v43: number;
  service: number;
  v42: number;
  v20: number;
  arrests: number;
  accidents: number;
  dead: number;
  injured: number;
}

interface ExecutiveChartsProps {
  stations: StationStat[];
}

export default function ExecutiveCharts({ stations }: ExecutiveChartsProps) {
  const categories = stations.map(st => `ส.ทล.${st.stationId}`);
  const v20Data = stations.map(st => st.v20);
  const arrestsData = stations.map(st => st.arrests);
  const accidentsData = stations.map(st => st.accidents);

  // Bar Chart Options: Comparison
  const barOptions: any = {
    chart: {
      type: 'bar',
      toolbar: { show: false },
      background: 'transparent',
    },
    theme: { mode: 'dark' },
    colors: ['#00f2ff', '#facc15', '#ef4444'],
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '55%',
        borderRadius: 4,
      },
    },
    dataLabels: { enabled: false },
    stroke: {
      show: true,
      width: 2,
      colors: ['transparent']
    },
    xaxis: {
      categories: categories,
      labels: { style: { colors: '#8b949e' } }
    },
    yaxis: {
      title: { text: 'จำนวนครั้ง/คดี', style: { color: '#8b949e' } },
      labels: { style: { colors: '#8b949e' } }
    },
    fill: { opacity: 1 },
    legend: {
      position: 'top',
      horizontalAlign: 'center',
      labels: { colors: '#8b949e' }
    },
    grid: { borderColor: '#30363d' }
  };

  const barSeries = [
    { name: 'ตั้งจุดตรวจ (ว.20)', data: v20Data },
    { name: 'จับกุม (คดี)', data: arrestsData },
    { name: 'อุบัติเหตุ', data: accidentsData }
  ];

  // Donut Chart: Accident Distribution
  const donutOptions: any = {
    chart: {
      type: 'donut',
      background: 'transparent',
    },
    theme: { mode: 'dark' },
    colors: ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'],
    labels: stations.map(st => `ส.ทล.${st.stationId}`),
    legend: {
      position: 'bottom',
      labels: { colors: '#8b949e' }
    },
    stroke: { show: false },
    dataLabels: { enabled: true }
  };

  const donutSeries = stations.map(st => st.accidents);

  return (
    <div className="row g-4 mt-2">
      <div className="col-lg-8 col-12">
        <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
          <h6 className="text-slate-300 font-bold mb-3">เปรียบเทียบผลงานและสถิติรายสถานี (กองกำกับ)</h6>
          <div className="chart-container">
            <Chart options={barOptions} series={barSeries} type="bar" height={320} />
          </div>
        </div>
      </div>

      <div className="col-lg-4 col-12">
        <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl h-100">
          <h6 className="text-slate-300 font-bold mb-3">สัดส่วนการเกิดอุบัติเหตุรายสถานี</h6>
          <div className="chart-container d-flex align-items-center justify-content-center" style={{ minHeight: '320px' }}>
            {donutSeries.reduce((a, b) => a + b, 0) === 0 ? (
              <p className="text-white-50 text-xs text-center py-5">ยังไม่มีสถิติอุบัติเหตุที่ได้รับอนุมัติในระบบ</p>
            ) : (
              <Chart options={donutOptions} series={donutSeries} type="donut" width={300} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
