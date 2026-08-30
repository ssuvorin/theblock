import { cx } from "@/lib/cx";

interface MeterProps {
  value: number;
  label?: string;
  cold?: boolean;
}

export function Meter({ value, label = "Strength", cold = false }: MeterProps) {
  const normalized = Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
  const rounded = Math.round(normalized);

  return (
    <div className={cx("meter-wrap", cold && "meter-cold")}>
      <div className="meter-meta">
        <span className="mono-label">{label}</span>
        <span className="meter-value">{rounded}</span>
      </div>
      <div
        className="meter-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={rounded}
      >
        <div className="meter-fill" style={{ width: `${rounded}%` }} />
      </div>
    </div>
  );
}
