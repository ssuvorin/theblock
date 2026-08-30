"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { GoalForm } from "@/components/GoalForm";
import { QueryAnswerView, type SelectedDraft } from "@/components/QueryAnswer";
import { SearchProgress } from "@/components/SearchProgress";
import { Badge, MonoLabel } from "@/components/ui";
import { ApiError, apiMessage, fetchApi } from "@/lib/api";
import type { DraftResponse, Opportunity, QueryAnswer, QueryResponse, WarmPathData } from "@/lib/types";

export default function QueryPage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<QueryAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draftBusyId, setDraftBusyId] = useState("");
  const [selectedDraft, setSelectedDraft] = useState<SelectedDraft | null>(null);

  async function runQuery(nextQuestion: string) {
    setQuestion(nextQuestion);
    setBusy(true);
    setAnswer(null);
    setSelectedDraft(null);
    setError("");
    try {
      const response = await fetchApi<QueryResponse>("/api/query", { method: "POST", body: { question: nextQuestion } });
      setAnswer({ ...response.answer, opportunities: response.answer.opportunities || [] });
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/login?next=/query");
        return;
      }
      setError(apiMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function prepareDraft(opportunity: Opportunity, path: WarmPathData) {
    setDraftBusyId(opportunity.opportunity_id);
    setError("");
    try {
      const response = await fetchApi<DraftResponse>(`/api/people/${path.person_id}/draft`, {
        method: "POST",
        body: { goal: question, opportunity_id: opportunity.opportunity_id, action: "reconnect", channel: "generic" },
      });
      setSelectedDraft({ draft: response.draft, opportunity, path });
      requestAnimationFrame(() => document.getElementById("draft-result")?.scrollIntoView({ behavior: "smooth" }));
    } catch (requestError) {
      setError(apiMessage(requestError));
    } finally {
      setDraftBusyId("");
    }
  }

  return (
    <AppShell title="Ask" topbarMeta={answer ? <Badge tone={answer.degraded ? "error" : "accent"}>{answer.evidence_quality} evidence</Badge> : undefined}>
      <div className="page"><div className="page-centered answer-stack">
        <header className="page-header"><div className="page-heading-block">
          <MonoLabel>Opportunity-first network search</MonoLabel>
          <h1 className="page-title">Find the opportunity. Find the person. Follow the warm path.</h1>
          <p className="page-subtitle">Current public roles are verified first. Only then are they connected to evidence in your private relationship memory.</p>
        </div></header>
        <GoalForm onSubmit={runQuery} busy={busy} />
        {busy && <SearchProgress />}
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span><span>{error}</span></div>}
        {answer && <QueryAnswerView answer={answer} question={question} draftBusyId={draftBusyId} selectedDraft={selectedDraft} onDraft={prepareDraft} />}
      </div></div>
    </AppShell>
  );
}
