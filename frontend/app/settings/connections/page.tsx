"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConnectionGrid } from "@/components/ConnectionGrid";
import { SettingsTabs } from "@/components/SettingsTabs";
import { Badge, Button, MonoLabel } from "@/components/ui";
import { apiMessage, fetchApi } from "@/lib/api";
import { useApiData } from "@/lib/useApi";
import type { Connection, ConnectionsResponse } from "@/lib/types";

type ConnectResponse = { redirect_url?: string; qr_code_base64?: string };

const loadConnections = () => fetchApi<ConnectionsResponse>("/api/connections");

function useConnections() {
  const { data, loaded, error, setError, reload } = useApiData(loadConnections);
  const [qrCode, setQrCode] = useState("");

  async function connect(source: string) {
    setError("");
    try {
      const response = await fetchApi<ConnectResponse>(`/api/connections/${source}/connect`, { method: "POST" });
      if (response.redirect_url) window.location.assign(response.redirect_url);
      else if (response.qr_code_base64) setQrCode(response.qr_code_base64);
    } catch (requestError) {
      setError(apiMessage(requestError));
    }
  }

  async function sync(connection: Connection) {
    try {
      await fetchApi(`/api/connections/${connection.id}/sync`, { method: "POST" });
      await reload();
    } catch (requestError) {
      setError(apiMessage(requestError));
    }
  }

  return { connections: data?.connections || [], loaded, error, qrCode, load: reload, connect, sync };
}

export default function ConnectionsPage() {
  const state = useConnections();
  return (
    <AppShell title="Sources" topbarMeta={<Badge>{state.loaded ? `${state.connections.length} configured` : "Reading"}</Badge>}>
      <div className="page">
        <SettingsTabs />
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Sources · read-only</MonoLabel>
            <h1 className="page-title">Everything you already wrote, flowing in.</h1>
            <p className="page-subtitle">Connection status and item counts come directly from each configured source.</p>
          </div>
          <Button variant="primary" onClick={state.load}>Refresh sources</Button>
        </header>
        {state.error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{state.error}</div>}
        <ConnectionGrid connections={state.connections} loaded={state.loaded} qrCode={state.qrCode} onConnect={state.connect} onSync={state.sync} />
      </div>
    </AppShell>
  );
}
