"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Avatar, Badge, Button, DataTable, EmptyState, Meter, MonoLabel, type DataColumn } from "@/components/ui";
import { ApiError, apiMessage, fetchApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PeopleResponse, PersonSummary } from "@/lib/types";

export function PeopleDirectory({ initialQuery }: { initialQuery: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [status, setStatus] = useState("");
  const [data, setData] = useState<PeopleResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const load = useCallback(async (q: string, nextStatus: string) => {
    const params = new URLSearchParams({ page: "1", limit: "50" });
    if (q.trim()) params.set("q", q.trim());
    if (nextStatus) params.set("status", nextStatus);
    try {
      setData(await fetchApi<PeopleResponse>(`/api/people?${params}`));
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/login");
        return;
      }
      setError(apiMessage(requestError));
    } finally {
      setBusy(false);
    }
  }, [router]);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ page: "1", limit: "50" });
    if (initialQuery.trim()) params.set("q", initialQuery.trim());
    fetchApi<PeopleResponse>(`/api/people?${params}`)
      .then((response) => { if (active) setData(response); })
      .catch((requestError) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) router.replace("/login");
        else setError(apiMessage(requestError));
      })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [initialQuery, router]);

  function filter(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    void load(query, status);
  }

  const columns: Array<DataColumn<PersonSummary>> = [
    { key: "name", label: "Name", render: (person) => <Link className="person-link" href={`/people/${person.id}`}><Avatar name={person.display_name} src={person.photo_url} size={28} /><span>{person.display_name}</span></Link> },
    { key: "role", label: "Role @ company", render: (person) => <span className="prose-tone">{[person.current_title, person.current_org].filter(Boolean).join(" @ ") || "—"}</span> },
    { key: "strength", label: "Strength", render: (person) => person.strength_score == null ? <span className="mono muted">—</span> : <Meter value={person.strength_score} cold={person.relationship_status !== "active"} /> },
    { key: "last", label: "Last contact", render: (person) => <span className="mono muted">{formatDate(person.last_interaction_at)}</span> },
    { key: "tags", label: "Tags", render: (person) => <span className="prose-tone">{person.tags?.join(", ") || "—"}</span> },
    { key: "sources", label: "Sources", render: (person) => <span className="source-list">{person.sources?.map((source) => <Badge key={source}>{source}</Badge>) || "—"}</span> },
  ];

  return (
    <AppShell title="People" topbarMeta={data ? <Badge>{data.total.toLocaleString()} total</Badge> : undefined}>
      <div className="page">
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>People · power-user view</MonoLabel>
            <h1 className="page-title">People you already know.</h1>
            <p className="page-subtitle">One person per relationship, with source provenance and advisory strength.</p>
          </div>
        </header>
        <form className="filter-bar" onSubmit={filter}>
          <label className="sr-only" htmlFor="people-filter">Filter people</label>
          <input id="people-filter" className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter by name, company, tag" />
          <label className="sr-only" htmlFor="status-filter">Relationship status</label>
          <select id="status-filter" className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All relationship states</option>
            <option value="active">Active</option>
            <option value="cold">Cold</option>
            <option value="dormant">Dormant</option>
          </select>
          <Button variant="primary" type="submit" disabled={busy}>Filter people</Button>
        </form>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        {busy && !data ? <div className="loading-panel">Reading people directory</div> : data?.people.length ? (
          <DataTable columns={columns} rows={data.people} rowKey={(person) => person.id} caption="People directory" />
        ) : (
          <EmptyState title="No people found">Try a broader query or import relationship data first.</EmptyState>
        )}
      </div>
    </AppShell>
  );
}
