import { DraftPanel } from "@/components/DraftPanel";
import { OpportunityCard } from "@/components/OpportunityCard";
import { PartnerReadout } from "@/components/PartnerReadout";
import { RelationshipGraph } from "@/components/RelationshipGraph";
import { EmptyState, MonoLabel } from "@/components/ui";
import type { Draft, Opportunity, QueryAnswer, WarmPathData } from "@/lib/types";

export type SelectedDraft = { draft: Draft; opportunity: Opportunity; path: WarmPathData };

const degradedNames: Record<string, string> = {
  context_dev_search: "Current market search is unavailable. Network-only results may be shown.",
  convex: "Private relationship retrieval is unavailable. Opportunities are shown without warm paths.",
};

function GoalSummary({ answer }: { answer: QueryAnswer }) {
  if (!answer.goal) return null;
  return (
    <section className="goal-grid" aria-label="Understood goal">
      <div className="goal-cell"><MonoLabel>Role</MonoLabel><strong>{answer.goal.role || "—"}</strong><span className="muted">{answer.goal.related_roles?.join(" · ") || "No related roles returned"}</span></div>
      <div className="goal-cell"><MonoLabel>Industry</MonoLabel><strong>{answer.goal.industry?.[0] || "—"}</strong><span className="muted">{answer.goal.industry?.slice(1).join(" · ") || "No related industries returned"}</span></div>
      <div className="goal-cell"><MonoLabel>Location</MonoLabel><strong>{answer.goal.location?.[0] || "—"}</strong><span className="muted">{answer.goal.location?.slice(1).join(" · ") || "No related locations returned"}</span></div>
    </section>
  );
}

interface QueryAnswerViewProps {
  answer: QueryAnswer;
  question: string;
  draftBusyId: string;
  selectedDraft: SelectedDraft | null;
  onDraft: (opportunity: Opportunity, path: WarmPathData) => void;
}

export function QueryAnswerView({ answer, question, draftBusyId, selectedDraft, onDraft }: QueryAnswerViewProps) {
  const warmPaths = answer.opportunities.flatMap((opportunity) => opportunity.warm_paths || []);
  return (
    <section className="answer-stack" aria-label="Query answer">
      <div className="query-quote">&gt; {question}</div>
      <div className="readout-row">
        <PartnerReadout partner="Context.dev" job="market search" count={answer.search?.sources_checked} unit="sources checked" live />
        <PartnerReadout partner="Convex" job="semantic index" />
        <PartnerReadout partner="Collabute" job="meeting import" />
      </div>
      {answer.degraded && (answer.degraded_components || ["unknown"]).map((component) => (
        <div className="degraded-banner" role="status" key={component}>
          <span className="banner-mark">△</span>
          <span>{degradedNames[component] || `${component} is temporarily unavailable. Partial evidence is shown.`}</span>
        </div>
      ))}
      {answer.search?.disclosure && (
        <div className="degraded-banner" role="status">
          <span className="banner-mark">D</span>
          <span>{answer.search.disclosure}</span>
        </div>
      )}
      <GoalSummary answer={answer} />
      <p className="answer-summary">{answer.summary}</p>
      {answer.opportunities.length ? (
        <div className="opportunity-list">
          {answer.opportunities.map((opportunity, index) => (
            <OpportunityCard key={opportunity.opportunity_id} opportunity={opportunity} rank={index + 1} onDraft={onDraft} draftBusy={draftBusyId === opportunity.opportunity_id} />
          ))}
        </div>
      ) : <EmptyState title="No supported current opportunities">No verified opportunity evidence was returned for this goal. We do not turn weak or missing sources into vacancies.</EmptyState>}
      {!!answer.network_candidates?.length && (
        <section className="card">
          <header className="card-header"><h2 className="card-title">Network-only candidates</h2></header>
          <div className="card-body">{answer.network_candidates.map((candidate) => <p key={candidate.person_id}><strong>{candidate.display_name}</strong> · {candidate.relevance_reason || "Goal-level relevance"}</p>)}</div>
        </section>
      )}
      {warmPaths.length > 0 && (
        <section className="answer-stack" aria-labelledby="graph-heading">
          <div><MonoLabel>Relationship graph</MonoLabel><h2 id="graph-heading">Evidence-backed paths</h2></div>
          <RelationshipGraph paths={warmPaths} />
        </section>
      )}
      {selectedDraft && (
        <div id="draft-result" className="answer-stack">
          <MonoLabel>Action · editable draft</MonoLabel>
          <DraftPanel {...selectedDraft} />
        </div>
      )}
    </section>
  );
}
