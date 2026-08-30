import Image from "next/image";
import { Badge, Button } from "@/components/ui";
import { formatDateTime, sourceCode } from "@/lib/format";
import type { Connection } from "@/lib/types";

const availableSources = ["gmail", "whatsapp", "collabute"] as const;

interface ConnectionGridProps {
  connections: Connection[];
  loaded: boolean;
  qrCode: string;
  onConnect: (source: string) => void;
  onSync: (connection: Connection) => void;
}

function ConnectionCard({ connection, onSync }: { connection: Connection; onSync: (connection: Connection) => void }) {
  const hasError = connection.status === "error" || Boolean(connection.last_error);
  return (
    <article className={`connection-card ${hasError ? "connection-card-error" : ""}`}>
      <div className="connection-title">
        <span className="source-mark">{sourceCode(connection.source)}</span>
        <div><strong>{connection.source}</strong><span className="citation-meta">{connection.external_account_id || "Account identifier unavailable"}</span></div>
      </div>
      <Badge tone={connection.status === "connected" ? "positive" : hasError ? "error" : "accent"}>{connection.status}</Badge>
      {connection.last_error && <span className="error-text">{connection.last_error}</span>}
      <div className="connection-meta"><span>Last sync</span><span>{formatDateTime(connection.last_sync_at)}</span></div>
      <Button variant="secondary" size="small" onClick={() => onSync(connection)}>Sync now</Button>
    </article>
  );
}

function AvailableCard({ source, onConnect }: { source: string; onConnect: (source: string) => void }) {
  return (
    <article className="connection-card">
      <div className="connection-title"><span className="source-mark">{sourceCode(source)}</span><strong>{source}</strong></div>
      <span className="prose-tone">Available as a read-only relationship source.</span>
      <Button variant="accent" size="small" onClick={() => onConnect(source)}>Connect</Button>
    </article>
  );
}

export function ConnectionGrid({ connections, loaded, qrCode, onConnect, onSync }: ConnectionGridProps) {
  if (!loaded) return <div className="loading-panel">Reading source connections</div>;
  const connectedSources = new Set(connections.map((item) => item.source));
  return (
    <>
      <section className="connection-grid" aria-label="Source connections">
        {connections.map((connection) => <ConnectionCard key={connection.id} connection={connection} onSync={onSync} />)}
        {availableSources.filter((source) => !connectedSources.has(source)).map((source) => <AvailableCard key={source} source={source} onConnect={onConnect} />)}
      </section>
      {qrCode && (
        <section className="card page-narrow" aria-label="WhatsApp connection code">
          <header className="card-header"><h2 className="card-title">Scan to connect</h2></header>
          <div className="card-body"><Image unoptimized src={qrCode} alt="WhatsApp connection QR code" width={240} height={240} /></div>
        </section>
      )}
    </>
  );
}
