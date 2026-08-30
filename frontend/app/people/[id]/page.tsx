"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Avatar, Badge, Card, EmptyState, Meter } from "@/components/ui";
import { ApiError, apiMessage, fetchApi } from "@/lib/api";
import { formatDate, formatDateTime, sourceCode } from "@/lib/format";
import type { PersonProfile, PersonResponse } from "@/lib/types";

function OrganizationName({ person }: { person: PersonProfile }) {
  if (!person.current_org) return <>—</>;
  return <>{typeof person.current_org === "string" ? person.current_org : person.current_org.name}</>;
}

export default function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [person, setPerson] = useState<PersonProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetchApi<PersonResponse>(`/api/people/${id}`)
      .then((response) => setPerson(response.person))
      .catch((requestError) => {
        if (requestError instanceof ApiError && requestError.status === 401) router.replace("/login");
        else setError(apiMessage(requestError));
      });
  }, [id, router]);

  return (
    <AppShell title="Person profile">
      <div className="page">
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        {!person && !error && <div className="loading-panel">Reading unified person memory</div>}
        {person && (
          <>
            <header className="profile-hero">
              <Avatar name={person.display_name} src={person.photo_url} size={64} path />
              <div className="profile-main">
                <div className="profile-title-row">
                  <h1>{person.display_name}</h1>
                  <span className="status-dot" aria-hidden="true" />
                  <span className="muted">{person.current_title || "Role unavailable"} · <OrganizationName person={person} /></span>
                </div>
                <div className="source-list">
                  {(person.source_badges || person.sources || []).map((source) => <Badge key={source}>{source}</Badge>)}
                </div>
              </div>
              {person.relationship?.strength_score != null && (
                <div className="w-40"><Meter value={person.relationship.strength_score} cold={person.relationship.status !== "active"} /></div>
              )}
            </header>
            <div className="profile-grid">
              <section className="timeline" aria-labelledby="timeline-title">
                <header className="card-header">
                  <h2 id="timeline-title" className="card-title">Unified timeline</h2>
                  <span className="mono muted">{person.relationship?.total_interactions?.toLocaleString() || "—"} entries</span>
                </header>
                {person.interactions?.length ? person.interactions.map((interaction) => (
                  <article className="timeline-entry" id={`interaction-${interaction.id}`} key={interaction.id}>
                    <span className="source-code">{sourceCode(interaction.source)}</span>
                    <div>
                      <div className="timeline-heading">
                        <strong>{interaction.subject || interaction.type}</strong>
                        <span className="timeline-date">{formatDateTime(interaction.occurred_at)}</span>
                      </div>
                      <p>{interaction.snippet || interaction.body_text || "No preview returned."}</p>
                    </div>
                  </article>
                )) : <EmptyState title="No timeline entries">No interactions were returned for this person.</EmptyState>}
              </section>
              <aside className="profile-aside" aria-label="Person details">
                <Card title="Relationship">
                  <dl className="definition-list">
                    <dt>Status</dt><dd>{person.relationship?.status || person.relationship_status || "—"}</dd>
                    <dt>Last contact</dt><dd>{formatDate(person.relationship?.last_interaction_at || person.last_interaction_at)}</dd>
                    {Object.entries(person.relationship?.strength_components || {}).map(([key, value]) => <><dt key={`${key}-label`}>{key.replaceAll("_", " ")}</dt><dd key={key}>{Math.round(value * 100)}%</dd></>)}
                  </dl>
                </Card>
                <Card title="Identities">
                  {person.identities?.length ? <dl className="definition-list">{person.identities.map((identity, index) => <><dt key={`${identity.kind}-${index}-label`}>{identity.kind}</dt><dd key={`${identity.kind}-${index}`}>{identity.value} {identity.verified && <Badge tone="positive">Verified</Badge>}</dd></>)}</dl> : <span className="muted">No identities returned.</span>}
                </Card>
                <Card title="Follow-ups">
                  {person.follow_ups?.length ? person.follow_ups.map((followup) => <p key={followup.id}>{followup.reason}<span className="citation-meta">{formatDate(followup.due_date)}</span></p>) : <span className="muted">No open follow-ups.</span>}
                </Card>
                <Card title="Documents">
                  {person.documents?.length ? person.documents.map((document) => <p key={document.id}>{document.url ? <a className="accent-text" href={document.url} target="_blank" rel="noreferrer">{document.name}</a> : document.name}</p>) : <span className="muted">No linked documents.</span>}
                </Card>
              </aside>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
