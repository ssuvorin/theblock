import { MonoLabel } from "@/components/ui/MonoLabel";

const steps = [
  ["01", "Understand the goal", "Resolve role, industry, location, and related titles."],
  ["02", "Search the market", "Check fresh public sources and verify current opportunity claims."],
  ["03", "Find warm paths", "Join supported opportunities to private relationship evidence."],
] as const;

export function SearchProgress() {
  return (
    <section className="search-progress" aria-live="polite" aria-label="Search in progress">
      {steps.map(([index, title, description]) => (
        <div className="progress-step progress-step-active" key={index}>
          <MonoLabel><span className="progress-dot" aria-hidden="true" />{index} · {title}</MonoLabel>
          <p>{description}</p>
        </div>
      ))}
    </section>
  );
}
