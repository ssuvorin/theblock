import { MonoLabel } from "@/components/ui/MonoLabel";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime } from "@/lib/format";
import type { PrivateCitation, PublicCitation } from "@/lib/types";

interface CitationBlockProps {
  kind: "public" | "private";
  citations: PublicCitation[] | PrivateCitation[];
}

function PublicItem({ citation }: { citation: PublicCitation }) {
  return (
    <li className="citation-item">
      <a href={citation.url} target="_blank" rel="noreferrer">{citation.title || citation.source_domain || citation.url}</a>
      {citation.excerpt && <span> — {citation.excerpt}</span>}
      <span className="citation-meta">{citation.source_domain || new URL(citation.url).hostname} · checked {formatDateTime(citation.checked_at)}</span>
    </li>
  );
}

function PrivateItem({ citation }: { citation: PrivateCitation }) {
  return (
    <li className="citation-item" id={`interaction-${citation.interaction_id}`}>
      <span>{citation.subject || citation.snippet || "Imported relationship evidence"}</span>
      <span className="citation-meta">{citation.source} · {formatDateTime(citation.occurred_at)} · interaction {citation.interaction_id}</span>
    </li>
  );
}

export function CitationBlock({ kind, citations }: CitationBlockProps) {
  const title = kind === "public" ? "Public opportunity sources" : "Private relationship sources";
  if (!citations.length) {
    return <EmptyState title={`${title} unavailable`}>No citation was returned for this evidence block.</EmptyState>;
  }
  return (
    <section className="citations" aria-label={title}>
      <MonoLabel>{title}</MonoLabel>
      <ul className="citation-list">
        {kind === "public"
          ? (citations as PublicCitation[]).map((citation) => <PublicItem key={citation.url} citation={citation} />)
          : (citations as PrivateCitation[]).map((citation) => <PrivateItem key={citation.interaction_id} citation={citation} />)}
      </ul>
    </section>
  );
}
