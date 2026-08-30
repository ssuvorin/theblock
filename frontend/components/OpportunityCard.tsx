import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { CitationBlock } from "@/components/CitationBlock";
import { VerificationBadge } from "@/components/VerificationBadge";
import { WarmPath } from "@/components/WarmPath";
import { cx } from "@/lib/cx";
import type { Opportunity, WarmPathData } from "@/lib/types";

interface OpportunityCardProps {
  opportunity: Opportunity;
  rank: number;
  onDraft: (opportunity: Opportunity, path: WarmPathData) => void;
  draftBusy?: boolean;
}

function cardTone(status: Opportunity["verification_status"]): string {
  if (status === "verified_open_role") return "opportunity-verified";
  if (status === "hiring_signal") return "opportunity-signal";
  if (status === "stale") return "opportunity-stale";
  return "";
}

export function OpportunityCard({ opportunity, rank, onDraft, draftBusy }: OpportunityCardProps) {
  const warmPath = opportunity.warm_paths?.[0];
  const organization = opportunity.organization;
  const organizationName = organization?.name || "Unresolved organization";
  return (
    <article className={cx("opportunity-card", cardTone(opportunity.verification_status))}>
      <div className="opportunity-main">
        <div className="opportunity-mark" aria-hidden="true">{String(rank).padStart(2, "0")}</div>
        <div>
          <div className="opportunity-heading">
            <h2>{organizationName}</h2>
            <span className="opportunity-role">{opportunity.role_title || "Market signal"}{opportunity.location ? ` · ${opportunity.location}` : ""}</span>
            <VerificationBadge status={opportunity.verification_status} />
          </div>
          <div className="opportunity-meta">
            {opportunity.goal_fit && <Badge tone="strong">Goal fit · {opportunity.goal_fit}</Badge>}
            {organization?.domain && <Badge>{organization.domain}</Badge>}
            {opportunity.warm_paths?.length > 1 && <Badge tone="accent">{opportunity.warm_paths.length} supported paths</Badge>}
          </div>
        </div>
      </div>
      <div className="opportunity-evidence">
        <div className="opportunity-column">
          <CitationBlock kind="public" citations={opportunity.public_citations || []} />
        </div>
        <div className="opportunity-column">
          {warmPath ? (
            <>
              <WarmPath path={warmPath} />
              <div className="draft-actions">
                <Button variant="primary" onClick={() => onDraft(opportunity, warmPath)} disabled={draftBusy}>
                  {draftBusy ? "Preparing draft" : "Draft message"}
                </Button>
              </div>
              <CitationBlock kind="private" citations={warmPath.private_citations || []} />
            </>
          ) : (
            <EmptyState title="No warm path found">No evidence-backed relationship path was found in your current network.</EmptyState>
          )}
        </div>
      </div>
    </article>
  );
}
