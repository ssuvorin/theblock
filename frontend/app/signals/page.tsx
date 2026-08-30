"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, EmptyState, MonoLabel, SignalCard } from "@/components/ui";
import { ApiError, apiMessage, fetchApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { FollowUp, FollowUpsResponse } from "@/lib/types";

function getMetrics(followups: FollowUp[], referenceTime: number) {
  const overdue = followups.filter((item) => item.due_date && new Date(item.due_date).getTime() < referenceTime).length;
  const high = followups.filter((item) => (item.priority ?? 0) >= 50).length;
  return { pending: followups.length, overdue, high };
}

export default function SignalsPage() {
  const router = useRouter();
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [referenceTime] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      const response = await fetchApi<FollowUpsResponse>("/api/followups?status=pending&sort=due_date");
      setFollowups(response.follow_ups || []);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) router.replace("/login");
      else setError(apiMessage(requestError));
    } finally {
      setLoaded(true);
    }
  }, [router]);

  useEffect(() => {
    let active = true;
    fetchApi<FollowUpsResponse>("/api/followups?status=pending&sort=due_date")
      .then((response) => { if (active) setFollowups(response.follow_ups || []); })
      .catch((requestError) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) router.replace("/login");
        else setError(apiMessage(requestError));
      })
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [router]);

  const metrics = getMetrics(followups, referenceTime);

  async function complete(item: FollowUp) {
    try {
      await fetchApi(`/api/followups/${item.id}`, { method: "PATCH", body: { status: "done" } });
      setFollowups((current) => current.filter((followup) => followup.id !== item.id));
    } catch (requestError) {
      setError(apiMessage(requestError));
    }
  }

  return (
    <AppShell title="Signals" topbarMeta={<Badge>{loaded ? `${followups.length} open` : "Reading"}</Badge>}>
      <div className="page page-centered">
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Signals · follow through before context goes cold</MonoLabel>
            <h1 className="page-title">What your relationship memory surfaced.</h1>
            <p className="page-subtitle">Follow-ups are sorted by due date and carry their source provenance.</p>
          </div>
          <Button variant="primary" onClick={load}>Refresh signals</Button>
        </header>
        <section className="metric-grid" aria-label="Signal summary">
          <div className="metric-card"><MonoLabel>Follow-ups due</MonoLabel><span className="metric-number">{metrics.pending}</span></div>
          <div className="metric-card"><MonoLabel>Overdue</MonoLabel><span className="metric-number">{metrics.overdue}</span></div>
          <div className="metric-card"><MonoLabel>High priority</MonoLabel><span className="metric-number">{metrics.high}</span></div>
        </section>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        {!loaded ? <div className="loading-panel">Reading follow-ups</div> : followups.length ? (
          <section className="signal-list" aria-label="Open follow-ups">
            {followups.map((item) => (
              <SignalCard key={item.id}>
                <div className="flex items-center gap-2"><Badge tone={(item.priority ?? 0) >= 50 ? "accent" : "neutral"}>{(item.priority ?? 0) >= 50 ? "high" : "normal"}</Badge><span className="ml-auto mono muted">{formatDate(item.due_date)}</span></div>
                <strong>{item.person?.display_name || "Relationship follow-up"}</strong>
                <span className="prose-tone">{item.reason}</span>
                <span className="mono muted">Source · {item.source || "manual"}</span>
                <Button variant="secondary" size="small" onClick={() => complete(item)}>Mark complete</Button>
              </SignalCard>
            ))}
          </section>
        ) : <EmptyState title="No open signals">Nothing is due. New reminders and imported action items will appear here.</EmptyState>}
      </div>
    </AppShell>
  );
}
