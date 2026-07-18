import { memo, useId } from "react";
import type { RegionalForecastDay } from "@/types/forecast";

const X_POINTS = [30, 92, 154, 216, 278, 340];

function chartY(value: number) {
  return 166 - (value / 150) * 132;
}

export const IntradayChart = memo(function IntradayChart({ day }: { day: RegionalForecastDay }) {
  const titleId = useId();
  const descriptionId = useId();
  const points = day.chartValues.map((item, index) => `${X_POINTS[index]},${chartY(item.value)}`).join(" ");

  return (
    <section className="forecast-glass forecast-chart-panel" aria-labelledby={titleId}>
      <h2 id={titleId}>Diễn biến trong ngày</h2>
      <p className="forecast-chart-caption">Chỉ số tổng hợp 24 giờ từ nguồn dự báo</p>
      <svg className="intraday-chart" viewBox="0 0 370 205" role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
        <desc id={descriptionId}>Các chỉ số nhiệt độ, lượng mưa, gió, độ ẩm và tầm nhìn trong ngày {day.dateLabel}.</desc>
        {[0, 50, 100, 150].map((value) => {
          const y = chartY(value);
          return (
            <g key={value}>
              <line x1="30" y1={y} x2="340" y2={y} className="chart-grid-line" />
              <text x="22" y={y + 4} textAnchor="end" className="chart-axis-label">{value}</text>
            </g>
          );
        })}
        <polyline points={points} className="chart-risk-line" style={{ stroke: day.accent }} />
        {day.chartValues.map((item, index) => (
          <g key={item.label}>
            <circle cx={X_POINTS[index]} cy={chartY(item.value)} r="3.5" className="chart-risk-dot" style={{ fill: day.accent }}>
              <title>{item.label}: {item.displayValue}</title>
            </circle>
            <text x={X_POINTS[index]} y="193" textAnchor="middle" className="chart-axis-label">{item.label}</text>
          </g>
        ))}
      </svg>
    </section>
  );
});
