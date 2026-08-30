import Link from "next/link";
import type { ReactNode } from "react";
import { Badge, Button, MonoLabel, buttonClassName } from "@/components/ui";
import { cx } from "@/lib/cx";

interface StepProps {
  index: string;
  title: string;
  requirement: string;
  status: ReactNode;
  tone?: "done" | "blocked";
  children: ReactNode;
}

interface OnboardingStepsProps {
  loaded: boolean;
  total?: number;
}

function Step({ index, title, requirement, status, tone, children }: StepProps) {
  return (
    <li className={cx("onboarding-step", tone && `onboarding-step-${tone}`)}>
      <span className="onboarding-step-index">{index}</span>
      <div className="onboarding-step-body">
        <MonoLabel>{requirement}</MonoLabel>
        <div className="onboarding-step-heading">
          <h2 className="onboarding-step-title">{title}</h2>
          {status}
        </div>
        {children}
      </div>
    </li>
  );
}

function ArchiveStatus({ loaded, imported }: { loaded: boolean; imported: boolean }) {
  if (!loaded) return <Badge>Reading graph</Badge>;
  return imported ? <Badge tone="positive">Archive imported</Badge> : <Badge tone="accent">Not done yet</Badge>;
}

function Finish({ loaded, imported }: { loaded: boolean; imported: boolean }) {
  return (
    <section className={cx("onboarding-finish", imported && "onboarding-finish-ready")} aria-label="After setup">
      <MonoLabel>Then</MonoLabel>
      <h2 className="onboarding-step-title">Ask something your own archive can answer.</h2>
      <p className="onboarding-step-note">{imported
        ? "Step 01 is done, so answers can cite real interactions from your graph instead of public text alone."
        : loaded
          ? "No imported people yet, so Ask has no private evidence of yours to cite. It stays reachable — it will just answer from public sources."
          : "Reading your graph to see whether an archive has been imported."}</p>
      <Link className={buttonClassName(imported ? "primary" : "secondary")} href="/query">{imported ? "Open Ask" : "Open Ask anyway"}</Link>
    </section>
  );
}

export function OnboardingSteps({ loaded, total }: OnboardingStepsProps) {
  const known = typeof total === "number";
  const imported = known && total > 0;
  return (
    <>
      <ol className="onboarding-steps">
        <Step index="01" title="Import your LinkedIn data archive" requirement="Required · file upload, no scraping" tone={imported ? "done" : undefined} status={<ArchiveStatus loaded={loaded} imported={imported} />}>
          <p className="onboarding-step-note">Request the export from LinkedIn, then upload the ZIP. Messages, invitations and connections become people, interactions and relationship edges, each carrying its source.</p>
          <div className="onboarding-step-actions">
            <Link className={buttonClassName(imported ? "secondary" : "primary")} href="/settings/imports">{imported ? "Import another archive" : "Import archive"}</Link>
            <span className="mono muted">People in graph · {known ? total.toLocaleString() : "—"}</span>
          </div>
        </Step>
        <Step index="02" title="Connect Google — Gmail, Calendar, Drive" requirement="Optional · not configured" tone="blocked" status={<Badge>Not configured</Badge>}>
          <p className="onboarding-step-note">No Google client is configured on this deployment. The connections endpoint returns an empty list and a connect call answers 409 not configured, so nothing is syncing in the background.</p>
          <div className="onboarding-step-actions">
            <Button variant="secondary" disabled>Connect Google</Button>
            <span className="mono muted">Connect endpoint · 409 not configured</span>
          </div>
        </Step>
        <Step index="03" title="Upload a CV (PDF)" requirement="Optional · not implemented" tone="blocked" status={<Badge>Not implemented</Badge>}>
          <p className="onboarding-step-note">CV parsing has no endpoint yet. When it exists it will fill the employment history and job titles that a LinkedIn Basic export leaves empty.</p>
          <div className="onboarding-step-actions">
            <Button variant="secondary" disabled>Upload CV</Button>
            <span className="mono muted">No endpoint yet</span>
          </div>
        </Step>
      </ol>
      <Finish loaded={loaded} imported={imported} />
    </>
  );
}
