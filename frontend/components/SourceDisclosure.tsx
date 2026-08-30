import { Badge } from "@/components/ui";
import type { SourceCatalogEntry } from "@/lib/types";

/**
 * The pre-sync consent disclosure required before a source is authorized.
 *
 * It renders the catalog entry verbatim, so what the owner reads here is what the OAuth
 * request will ask for — a scope cannot appear in the request without appearing on screen.
 * `details`/`summary` keeps it collapsed without costing keyboard access.
 */
export function SourceDisclosure({ source }: { source: SourceCatalogEntry }) {
  const scopes = source.scopes.length ? source.scopes : ["No scopes are requested."];
  return (
    <details className="source-disclosure">
      <summary className="source-disclosure-summary">
        What this reads
        {source.write_access && (
          <Badge tone="accent" className="source-write-flag">
            can write
          </Badge>
        )}
      </summary>
      <div className="source-disclosure-body">
        <p className="prose-tone">{source.disclosure}</p>
        <dl className="definition-list">
          <dt>Access</dt>
          <dd>{source.write_access ? "Read and write" : "Read only"}</dd>
          <dt>Scopes</dt>
          <dd>
            <ul className="scope-list">
              {scopes.map((scope) => (
                <li key={scope}>{shortScope(scope)}</li>
              ))}
            </ul>
          </dd>
          <dt>Lookback</dt>
          <dd>{source.lookback_days ? `${source.lookback_days} days` : "—"}</dd>
          <dt>Processors</dt>
          <dd>{source.processors.length ? source.processors.join(", ") : "None"}</dd>
        </dl>
      </div>
    </details>
  );
}

/** Google scope URLs are unreadable in full; the trailing segment is the meaningful part. */
function shortScope(scope: string): string {
  const trimmed = scope.replace(/^https:\/\/www\.googleapis\.com\/auth\//, "");
  return trimmed || scope;
}
