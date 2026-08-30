"use client";

import { Fragment } from "react";
import { AppShell } from "@/components/AppShell";
import { PartnerReadout } from "@/components/PartnerReadout";
import { SettingsTabs } from "@/components/SettingsTabs";
import { Badge, Card, MonoLabel } from "@/components/ui";
import { fetchApi } from "@/lib/api";
import { useApiData } from "@/lib/useApi";
import type { ConnectionsResponse } from "@/lib/types";

type DependencyStatus = Record<string, unknown> & {
  context_dev?: { credits_remaining?: number; web_search?: string; brand_retrieve?: string };
};

const loadData = async () => {
  const [connections, dependencies] = await Promise.all([
    fetchApi<ConnectionsResponse>("/api/connections"),
    fetchApi<DependencyStatus>("/api/health/deps"),
  ]);
  return { connections, dependencies };
};

export default function DataPage() {
  const { data, error } = useApiData(loadData);
  const connections = data?.connections;
  const dependencies = data?.dependencies;

  return (
    <AppShell title="Data & privacy">
      <div className="page page-narrow">
        <SettingsTabs />
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Data & privacy</MonoLabel>
            <h1 className="page-title">See exactly what the system can read.</h1>
            <p className="page-subtitle">Source connections are read-only. Public opportunity citations and private interaction citations are stored and displayed separately.</p>
          </div>
        </header>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        <div className="readout-row">
          <PartnerReadout partner="Context.dev" job="market search credits remaining" count={dependencies?.context_dev?.credits_remaining} />
          <PartnerReadout partner="Convex" job="semantic index" />
          <PartnerReadout partner="Collabute" job="meeting import" />
        </div>
        <Card title="Connected data sources" meta={<Badge>{connections ? connections.connections.length : "—"} configured</Badge>}>
          {connections?.connections.length ? connections.connections.map((connection) => (
            <div className="connection-meta" key={connection.id}>
              <span>{connection.source} · {connection.external_account_id || "account unavailable"}</span>
              <Badge tone={connection.status === "connected" ? "positive" : "error"}>{connection.status}</Badge>
            </div>
          )) : <span className="muted">No configured sources were returned.</span>}
        </Card>
        <Card title="Evidence boundaries">
          <dl className="definition-list">
            <dt>Public market</dt><dd>Current role claims require a URL, source domain, and checked time.</dd>
            <dt>Private memory</dt><dd>Relationship claims require an imported interaction or owner-created edge.</dd>
            <dt>Automatic delivery</dt><dd>Disabled. Draft actions stop at copy, external handoff, reminders, and save.</dd>
            <dt>LinkedIn</dt><dd>File import only. No login, crawling, or credential collection.</dd>
          </dl>
        </Card>
        <Card title="Dependency read-out">
          {dependencies ? <dl className="definition-list">{Object.entries(dependencies).map(([name, value]) => <Fragment key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd></Fragment>)}</dl> : <span className="muted">Dependency status unavailable.</span>}
        </Card>
      </div>
    </AppShell>
  );
}
