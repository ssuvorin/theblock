import { Badge, MonoLabel } from "@/components/ui";
import { cx } from "@/lib/cx";
import type { ImportWritten, LinkedInImportReport } from "@/lib/types";

const ownerNote = "Profile.csv carries no URL column, so the owner's own LinkedIn URL is derived from invitation and message evidence. Every imported message is attributed from that one resolution.";
const titleNote = "A LinkedIn Basic export ships no job titles for contacts, so contacts without a title are expected here. Titles arrive later from CV uploads, email signatures and organization enrichment.";
const dryNote = "Graph counts appear after a real import. A validation run parses the archive and reports nothing written.";

function count(value?: number | null): string {
  return typeof value === "number" ? value.toLocaleString() : "—";
}

function Readout({ label, value }: { label: string; value?: number | null }) {
  return (
    <div className="import-readout">
      <MonoLabel>{label}</MonoLabel>
      <span className="import-readout-value">{count(value)}</span>
    </div>
  );
}

interface PairProps {
  label: string;
  freshLabel: string;
  fresh?: number | null;
  keptLabel: string;
  kept?: number | null;
  note: string;
}

function Pair({ label, freshLabel, fresh, keptLabel, kept, note }: PairProps) {
  return (
    <div className="import-pair">
      <MonoLabel>{label}</MonoLabel>
      <div className="import-pair-figures">
        <span className="import-pair-figure"><strong>{count(fresh)}</strong>{freshLabel}</span>
        <span className="import-pair-figure import-pair-kept"><strong>{count(kept)}</strong>{keptLabel}</span>
      </div>
      <p className="import-pair-note">{note}</p>
    </div>
  );
}

function OwnerResolution({ resolution }: { resolution?: LinkedInImportReport["owner_resolution"] }) {
  const method = resolution?.method || "";
  const confidence = resolution?.confidence || "";
  const weak = !method || method === "unresolved" || confidence === "low" || confidence === "none";
  return (
    <section className={cx("import-owner", weak && "import-owner-weak")} aria-label="Owner resolution">
      <div className="import-row">
        <MonoLabel>Owner resolution</MonoLabel>
        <span className="prose-tone">Method · {method || "—"}</span>
        <Badge tone={weak ? "error" : "positive"}>{confidence || "—"} confidence</Badge>
      </div>
      <p className="import-note">{ownerNote}</p>
      {weak && <p className="error-text">Self-attribution is unverified until the owner URL resolves, so treat direction and reciprocity on these messages as unproven.</p>}
    </section>
  );
}

function ParseCounts({ report }: { report: LinkedInImportReport }) {
  return (
    <section className="import-readout-grid" aria-label="Parsed archive">
      <Readout label="Messages" value={report.messages} />
      <Readout label="Conversations" value={report.conversations} />
      <Readout label="People proposed" value={report.people_proposed} />
      <Readout label="Unique identities" value={report.unique_identities} />
      <Readout label="Empty messages" value={report.empty_messages} />
      <Readout label="Drafts skipped" value={report.drafts_skipped} />
      <Readout label="Chunks proposed" value={report.chunks_proposed} />
      <Readout label="Connections seen" value={report.connections_seen} />
      <Readout label="Connections matched" value={report.connections_matched} />
    </section>
  );
}

function GraphWrites({ written }: { written: ImportWritten }) {
  return (
    <section className="import-writes" aria-label="Graph writes">
      <div className="import-row">
        <MonoLabel>Written to the graph</MonoLabel>
        <span className="import-note">Second column proves a re-import stays idempotent.</span>
      </div>
      <Pair label="People" fresh={written.people_created} freshLabel="created" kept={written.people_matched} keptLabel="matched to people already in the graph" note="Matched people were resolved by LinkedIn identity and updated in place, so running this archive again does not create a second copy of anyone." />
      <Pair label="Interactions" fresh={written.interactions_created} freshLabel="created" kept={written.interactions_existing} keptLabel="already present, skipped" note="Already present means the message identifier was recognised from an earlier run, so the same message is never stored twice." />
      <Pair label="Relationships" fresh={written.relationships_created} freshLabel="created" kept={written.relationships_updated} keptLabel="updated in place" note="Updated edges recalculate an existing relationship instead of adding a second edge between the same two people." />
      <div className="import-readout-grid">
        <Readout label="Identities created" value={written.identities_created} />
        <Readout label="Participants created" value={written.participants_created} />
        <Readout label="Contacts without title" value={written.contacts_without_title} />
      </div>
      <p className="import-note">{titleNote}</p>
      <div className="import-row">
        <MonoLabel>Self person</MonoLabel>
        <span className="mono muted">{written.self_person_id || "—"}</span>
        <MonoLabel>Data origin</MonoLabel>
        <span className="mono muted">{written.data_origin || "—"}</span>
      </div>
    </section>
  );
}

function Warnings({ warnings }: { warnings?: string[] }) {
  if (!warnings?.length) return null;
  return (
    <section className="import-warnings" aria-label="Importer warnings">
      <MonoLabel>Warnings · {warnings.length}</MonoLabel>
      <ul className="import-warning-list">
        {warnings.map((warning) => <li className="import-warning" key={warning}>{warning}</li>)}
      </ul>
    </section>
  );
}

export function ImportReport({ report }: { report: LinkedInImportReport }) {
  const written = report.written;
  const persisted = Boolean(written) && report.persistence !== "dry_run";
  return (
    <section className="import-readout-stack" aria-label="Import report">
      <header className={cx("import-status", persisted ? "import-status-written" : "import-status-dry")}>
        <div className="import-row">
          <MonoLabel>Result</MonoLabel>
          <Badge tone={persisted ? "positive" : "accent"}>{persisted ? "Data written" : "Nothing written"}</Badge>
        </div>
        <strong className="import-status-headline">{persisted ? "The archive is now part of your graph." : "Validated only. Your graph is unchanged."}</strong>
        <p className="import-note">Status · {report.status || "—"} · storage · {report.persistence || "—"} · data origin · {report.data_origin || "—"}</p>
      </header>
      <ParseCounts report={report} />
      <OwnerResolution resolution={report.owner_resolution} />
      {written ? <GraphWrites written={written} /> : <p className="import-note">{dryNote}</p>}
      <Warnings warnings={report.warnings} />
    </section>
  );
}
