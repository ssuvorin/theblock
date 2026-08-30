import { Badge, Button } from "@/components/ui";
import { SourceDisclosure } from "@/components/SourceDisclosure";
import { formatDateTime, sourceCode } from "@/lib/format";
import type { Connection, SourceCatalogEntry } from "@/lib/types";

const STATUS_TONES: Record<string, "positive" | "error" | "accent" | "neutral"> = {
  connected: "positive",
  syncing: "accent",
  authorizing: "accent",
  degraded: "error",
  reauth_required: "error",
  error: "error",
  disconnected: "neutral",
};

export interface ConnectionActions {
  onConnect: (source: SourceCatalogEntry) => void;
  onSync: (connection: Connection) => void;
  onTogglePause: (connection: Connection) => void;
  onDisconnect: (connection: Connection) => void;
  onInspect: (connection: Connection) => void;
}

interface ConnectionGridProps extends ConnectionActions {
  catalog: SourceCatalogEntry[];
  connections: Connection[];
  loaded: boolean;
  busy?: string;
}

/**
 * Renders the source catalog, not a hardcoded list.
 *
 * A source the deployment cannot use shows why instead of offering a button that would 409,
 * which is the difference between an honest empty state and a broken one.
 */
export function ConnectionGrid({
  catalog,
  connections,
  loaded,
  busy,
  ...actions
}: ConnectionGridProps) {
  if (!loaded) return <div className="loading-panel">Reading source connections</div>;
  const linked = new Map(connections.map((item) => [item.source, item]));
  return (
    <section className="connection-grid" aria-label="Source connections">
      {catalog.map((source) => {
        const connection = linked.get(source.source);
        // `consent_granted_at` is the only field that proves a grant landed; a row that only
        // reached `authorizing` still needs the connect button, not a sync button.
        return connection?.consent_granted_at ? (
          <ConnectionCard
            key={source.source}
            source={source}
            connection={connection}
            busy={busy}
            {...actions}
          />
        ) : (
          <AvailableCard key={source.source} source={source} busy={busy} {...actions} />
        );
      })}
    </section>
  );
}

function ConnectionCard({
  source,
  connection,
  busy,
  onSync,
  onTogglePause,
  onDisconnect,
  onInspect,
}: { source: SourceCatalogEntry; connection: Connection; busy?: string } & ConnectionActions) {
  const failing = ["error", "degraded", "reauth_required"].includes(connection.status);
  return (
    <article className={`connection-card ${failing ? "connection-card-error" : ""}`}>
      <SourceHeading source={source} account={connection.external_account_id} />
      <div className="connection-badges">
        <Badge tone={STATUS_TONES[connection.status] ?? "neutral"}>{connection.status}</Badge>
        {connection.paused && <Badge>paused</Badge>}
      </div>
      {connection.status === "reauth_required" && (
        <p className="error-text">Access expired. Reconnect to grant it again.</p>
      )}
      {connection.last_error && <p className="error-text">{connection.last_error}</p>}
      <SourceDisclosure source={source} />
      <div className="connection-meta">
        <span>Last sync</span>
        <span>{formatDateTime(connection.last_sync_at)}</span>
      </div>
      <div className="connection-actions">
        <Button
          variant="accent"
          size="small"
          disabled={connection.paused || busy === connection.id}
          onClick={() => onSync(connection)}
        >
          {busy === connection.id ? "Syncing" : "Sync now"}
        </Button>
        <Button size="small" onClick={() => onTogglePause(connection)}>
          {connection.paused ? "Resume" : "Pause"}
        </Button>
        <Button size="small" variant="ghost" onClick={() => onInspect(connection)}>
          History
        </Button>
        <Button size="small" variant="ghost" onClick={() => onDisconnect(connection)}>
          Disconnect
        </Button>
      </div>
    </article>
  );
}

function AvailableCard({
  source,
  busy,
  onConnect,
}: { source: SourceCatalogEntry; busy?: string } & ConnectionActions) {
  const available = source.availability === "available";
  return (
    <article className={`connection-card ${available ? "" : "connection-card-muted"}`}>
      <SourceHeading source={source} account={null} />
      <Badge tone={available ? "accent" : "neutral"}>
        {available ? "not connected" : source.availability.replace("_", " ")}
      </Badge>
      {!available && <p className="prose-tone">{source.reason ?? source.disclosure}</p>}
      {!available && source.requirements.length > 0 && (
        <p className="citation-meta">Needs: {source.requirements.join(", ")}</p>
      )}
      {available && <SourceDisclosure source={source} />}
      {available && (
        <Button
          variant="accent"
          size="small"
          disabled={busy === source.source}
          onClick={() => onConnect(source)}
        >
          {busy === source.source ? "Opening" : "Review and connect"}
        </Button>
      )}
    </article>
  );
}

function SourceHeading({
  source,
  account,
}: {
  source: SourceCatalogEntry;
  account?: string | null;
}) {
  return (
    <div className="connection-title">
      <span className="source-mark">{sourceCode(source.source)}</span>
      <div>
        <strong>{source.label}</strong>
        <span className="citation-meta">{account || source.surfaces.join(" · ")}</span>
      </div>
    </div>
  );
}
