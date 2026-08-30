interface PartnerReadoutProps {
  partner: string;
  job: string;
  count?: number | null;
  unit?: string;
  live?: boolean;
}

export function PartnerReadout({ partner, job, count, unit, live = false }: PartnerReadoutProps) {
  const value = typeof count === "number" ? count.toLocaleString() : "—";

  return (
    <span className="partner-readout">
      {live && <span className="readout-live" aria-hidden="true" />}
      <span className="partner-name">{partner}</span>
      <span>· {job} · {value}{typeof count === "number" && unit ? ` ${unit}` : ""}</span>
    </span>
  );
}
