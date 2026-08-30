"use client";

import { useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { MonoLabel } from "@/components/ui/MonoLabel";
import { CitationBlock } from "@/components/CitationBlock";
import { apiMessage, fetchApi } from "@/lib/api";
import type { Draft, Opportunity, WarmPathData } from "@/lib/types";

interface DraftPanelProps {
  draft: Draft;
  opportunity: Opportunity;
  path: WarmPathData;
}

export function DraftPanel({ draft, opportunity, path }: DraftPanelProps) {
  const [text, setText] = useState(draft.text);
  const [status, setStatus] = useState("Draft is editable and remains under your control.");
  const organization = opportunity.organization?.name || "Unresolved organization";

  async function copyDraft() {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Copied to clipboard.");
    } catch (error) {
      setStatus(apiMessage(error));
    }
  }

  function openExternalClient() {
    const subject = draft.subject || `Regarding ${opportunity.role_title || organization}`;
    const url = draft.external_url || `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
    window.location.assign(url);
  }

  async function createReminder() {
    try {
      await fetchApi("/api/followups", {
        method: "POST",
        body: { person_id: path.person_id, reason: `Follow up with ${path.display_name} about ${organization}` },
      });
      setStatus("Reminder created.");
    } catch (error) {
      setStatus(apiMessage(error));
    }
  }

  async function saveOpportunity() {
    try {
      await fetchApi(`/api/opportunities/${opportunity.opportunity_id}`, { method: "PATCH", body: { saved: true } });
      setStatus("Opportunity saved.");
    } catch (error) {
      setStatus(apiMessage(error));
    }
  }

  return (
    <section className="draft-panel" aria-labelledby="draft-title">
      <div className="draft-context">
        <div className="draft-person">
          <Avatar name={path.display_name} size={56} path />
          <div>
            <h2 id="draft-title">{path.display_name}</h2>
            <span className="muted">{path.current_role || "Relationship contact"}</span>
          </div>
        </div>
        <div className="context-block">
          <MonoLabel>Relationship context</MonoLabel>
          <p>{path.relevance_reason || "Grounded in imported relationship evidence."}</p>
        </div>
        <div className="context-block">
          <MonoLabel>Why now</MonoLabel>
          <p>{opportunity.role_title || "Relevant activity"} at {organization}{opportunity.location ? ` · ${opportunity.location}` : ""}.</p>
        </div>
        <div className="context-block">
          <CitationBlock kind="private" citations={draft.private_citations || []} />
        </div>
      </div>
      <div className="draft-editor">
        <MonoLabel>Editable draft · no automatic delivery</MonoLabel>
        <label className="sr-only" htmlFor="draft-text">Edit draft message</label>
        <textarea id="draft-text" className="textarea" value={text} onChange={(event) => setText(event.target.value)} />
        <div className="draft-actions">
          <Button variant="primary" onClick={copyDraft}>Copy</Button>
          <Button variant="secondary" onClick={openExternalClient}>Open external client</Button>
          <Button variant="secondary" onClick={createReminder}>Remind me</Button>
          <Button variant="secondary" onClick={saveOpportunity}>Save opportunity</Button>
        </div>
        <div className="action-status" role="status">{status}</div>
        <CitationBlock kind="public" citations={draft.public_citations || opportunity.public_citations || []} />
      </div>
    </section>
  );
}
