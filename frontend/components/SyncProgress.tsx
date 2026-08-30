import { Badge } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { SyncRun } from "@/lib/types";

const TONES: Record<string, "positive" | "error" | "accent" | "neutral"> = {
  succeeded: "positive",
  partial: "accent",
  failed: "error",
  running: "accent",
};

const COUNTER_LABELS: Record<string, string> = {
  people_created: "people added",
  interactions_created: "items added",
  interactions_updated: "items updated",
  participants_unresolved: "unresolved participants",
  relationships_created: "connections added",
  relationships_updated: "connections updated",
  followups_created: "reminders created",
  action_items_unassigned: "action items unassigned",
  semantic_queued: "queued for indexing",
  shared_addresses_skipped: "shared addresses skipped",
};

/**
 * Per-run sync progress (FR-12.1): processed, skipped and error counts, plus a readable error.
 *
 * Every number is read off the recorded run. Nothing here is derived or estimated, so an empty
 * sync says zero rather than implying work that did not happen.
 */
export function SyncProgress({ runs }: { runs: SyncRun[] }) {
  if (!runs.length) {
    return <p className="muted">This source has not been synced yet.</p>;
  }
  return (
    <ol className="sync-run-list">
      {runs.map((run) => (
        <li key={run.id} className="sync-run">
          <div className="sync-run-head">
            <Badge tone={TONES[run.status] ?? "neutral"}>{run.status}</Badge>
            <span className="citation-meta">{run.mode} · {formatDateTime(run.started_at)}</span>
          </div>
          <div className="sync-run-counts">
            <span>{run.processed} processed</span>
            <span>{run.skipped} skipped</span>
            <span>{run.errors} errors</span>
          </div>
          {describe(run).length > 0 && (
            <p className="citation-meta">{describe(run).join(" · ")}</p>
          )}
          {run.error_message && <p className="error-text">{run.error_message}</p>}
        </li>
      ))}
    </ol>
  );
}

function describe(run: SyncRun): string[] {
  const counters = run.counters ?? {};
  return Object.entries(COUNTER_LABELS)
    .map(([key, label]) => ({ label, value: counters[key] }))
    .filter((entry) => typeof entry.value === "number" && entry.value > 0)
    .map((entry) => `${String(entry.value)} ${entry.label}`);
}
