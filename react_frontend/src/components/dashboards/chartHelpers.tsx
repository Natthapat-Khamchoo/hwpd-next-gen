import ReactApexChartImport from 'react-apexcharts';

// react-apexcharts ships as CommonJS; normalize the default export for Vite interop
// (otherwise Vite throws "Element type is invalid ... got: object").
export const ReactApexChart = ((ReactApexChartImport as any).default ?? ReactApexChartImport) as typeof ReactApexChartImport;

const GRID = { borderColor: '#30363d', strokeDashArray: 4 };

export const hBarOptions = (categories: string[], color = '#facc15'): ApexCharts.ApexOptions => ({
  chart: { type: 'bar', height: 320, toolbar: { show: false }, background: 'transparent' },
  theme: { mode: 'dark' },
  colors: [color],
  plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
  dataLabels: { enabled: true, textAnchor: 'start', style: { colors: ['#000'], fontSize: '13px', fontWeight: 'bold' }, offsetX: 15 },
  xaxis: { categories, labels: { style: { colors: '#8b949e' } } },
  yaxis: { labels: { style: { colors: '#fff', fontWeight: 'bold' } } },
  legend: { show: false },
  grid: GRID,
  tooltip: { theme: 'dark' },
});

export const vBarOptions = (categories: string[], colors: string[] = ['#0dcaf0']): ApexCharts.ApexOptions => ({
  chart: { type: 'bar', height: 320, toolbar: { show: false }, background: 'transparent', stacked: false },
  theme: { mode: 'dark' },
  colors,
  plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
  dataLabels: { enabled: false },
  xaxis: { categories, labels: { style: { colors: '#8b949e' } } },
  yaxis: { labels: { style: { colors: '#8b949e' } } },
  legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#fff' } },
  grid: GRID,
  tooltip: { theme: 'dark' },
});

export const lineOptions = (categories: string[], colors: string[]): ApexCharts.ApexOptions => ({
  chart: { type: 'line', height: 320, toolbar: { show: false }, background: 'transparent' },
  theme: { mode: 'dark' },
  colors,
  stroke: { curve: 'smooth', width: 3 },
  xaxis: { categories, labels: { style: { colors: '#8b949e' } } },
  yaxis: { labels: { style: { colors: '#8b949e' } } },
  legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#fff' } },
  grid: GRID,
  tooltip: { theme: 'dark' },
});

export const donutOptions = (labels: string[], colors?: string[]): ApexCharts.ApexOptions => ({
  chart: { type: 'donut', height: 320, background: 'transparent' },
  theme: { mode: 'dark' },
  labels,
  ...(colors ? { colors } : {}),
  legend: { position: 'bottom', labels: { colors: '#fff' } },
  tooltip: { theme: 'dark' },
});
