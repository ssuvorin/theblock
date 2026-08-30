"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConnectionGrid } from "@/components/ConnectionGrid";
import { ScheduleMeetingForm } from "@/components/ScheduleMeetingForm";
import { SettingsTabs } from "@/components/SettingsTabs";
import { SyncProgress } from "@/components/SyncProgress";
import { Badge, Button, Card, MonoLabel } from "@/components/ui";
import { useConnections } from "@/lib/useConnections";
import type { Connection } from "@/lib/types";

export default function ConnectionsPage() {
  const state = useConnections();
  const [pendingDelete, setPendingDelete] = useState<Connection | null>(null);
  const google = state.catalog.find((item) => item.source === "google");
  const scheduling = Boolean(google?.write_access);
  const googleConnected = state.connections.some(
    (item) => item.source === "google" && item.consent_granted_at,
  );

  return (
    <AppShell
      title="Sources"
      topbarMeta={
        <Badge>{state.loaded ? `${state.connections.length} connected` : "Reading"}</Badge>
      }
    >
      <div className="page">
        <SettingsTabs />
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Sources</MonoLabel>
            <h1 className="page-title">Everything you already wrote, flowing in.</h1>
            <p className="page-subtitle">
              Each source states what it reads before you authorize it. Ingestion is read-only;
              only meeting scheduling can write, and only when you press the button.
            </p>
          </div>
          <Button variant="primary" onClick={() => void state.reload()}>
            Refresh sources
          </Button>
        </header>

        <div aria-live="polite">
          {state.outcome && (
            <div
              className={state.outcome.status === "ok" ? "notice-strip" : "degraded-banner"}
              role="alert"
            >
              <span className="banner-mark">{state.outcome.status === "ok" ? "✓" : "×"}</span>
              {state.outcome.status === "ok"
                ? `${state.outcome.source} is connected. Run a sync to import it.`
                : `${state.outcome.source} was not connected: ${state.outcome.reason ?? "unknown reason"}`}
            </div>
          )}
          {state.error && (
            <div className="degraded-banner" role="alert">
              <span className="banner-mark">×</span>
              {state.error}
            </div>
          )}
        </div>

        <ConnectionGrid
          catalog={state.catalog}
          connections={state.connections}
          loaded={state.loaded}
          busy={state.busy}
          onConnect={(source) => void state.connect(source)}
          onSync={(connection) => void state.sync(connection)}
          onTogglePause={(connection) => void state.togglePause(connection)}
          onDisconnect={setPendingDelete}
          onInspect={(connection) => void state.inspect(connection)}
        />

        {pendingDelete && (
          <DisconnectConfirm
            connection={pendingDelete}
            onCancel={() => setPendingDelete(null)}
            onConfirm={(deleteData) => {
              void state.disconnect(pendingDelete, deleteData);
              setPendingDelete(null);
            }}
          />
        )}

        {state.history && (
          <Card
            title={`Sync history · ${state.history.source}`}
            meta={
              <Button size="small" variant="ghost" onClick={state.clearHistory}>
                Close
              </Button>
            }
          >
            <SyncProgress runs={state.history.sync_runs} />
          </Card>
        )}

        <ScheduleMeetingForm
          enabled={scheduling && googleConnected}
          reason={schedulingReason(scheduling, googleConnected)}
        />
      </div>
    </AppShell>
  );
}

function schedulingReason(scheduling: boolean, connected: boolean): string | undefined {
  if (!scheduling) {
    return (
      "Scheduling is off on this deployment. Set GOOGLE_MEETING_SCHEDULING=true and reconnect " +
      "Google so it can consent to the calendar write scope."
    );
  }
  if (!connected) return "Connect Google first — a meeting is created in your own calendar.";
  return undefined;
}

function DisconnectConfirm({
  connection,
  onCancel,
  onConfirm,
}: {
  connection: Connection;
  onCancel: () => void;
  onConfirm: (deleteData: boolean) => void;
}) {
  return (
    <Card title={`Disconnect ${connection.source}?`} meta={<Badge tone="error">irreversible</Badge>}>
      <p className="prose-tone">
        Disconnecting revokes the credentials and stops syncing. You can also delete what this
        source imported — people who are still evidenced by another source are kept.
      </p>
      <div className="connection-actions">
        <Button size="small" onClick={() => onConfirm(false)}>
          Disconnect, keep imported data
        </Button>
        <Button size="small" variant="accent" onClick={() => onConfirm(true)}>
          Disconnect and delete imported data
        </Button>
        <Button size="small" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </Card>
  );
}
