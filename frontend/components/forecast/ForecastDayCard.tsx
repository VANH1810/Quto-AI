import { Droplets, Wind } from "lucide-react";
import type { CSSProperties } from "react";
import { memo } from "react";
import type { RegionalForecastDay } from "@/types/forecast";

interface ForecastDayCardProps {
  day: RegionalForecastDay;
  isActive: boolean;
  onSelect: (id: string) => void;
}

export const ForecastDayCard = memo(function ForecastDayCard({ day, isActive, onSelect }: ForecastDayCardProps) {
  const style = {
    "--forecast-accent": day.accent,
    "--forecast-tint": day.tint,
  } as CSSProperties;

  return (
    <button
      className={`forecast-day-card${isActive ? " is-active" : ""}`}
      type="button"
      aria-pressed={isActive}
      aria-label={`${day.dateLabel}: ${day.cardHazardLabel}, ${day.cardTemperature} độ C`}
      style={style}
      onClick={() => onSelect(day.id)}
    >
      <span className="forecast-day-temperature">
        <strong>{day.dateLabel}</strong>
        <b>{day.cardTemperature}°C</b>
      </span>
      <span className="forecast-day-facts">
        <strong>{day.cardHazardLabel}</strong>
        <small><Droplets aria-hidden="true" />{day.rainfall}mm</small>
        <small><Wind aria-hidden="true" />{day.windSpeed}km/h</small>
      </span>
    </button>
  );
});
