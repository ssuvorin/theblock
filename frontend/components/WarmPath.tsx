import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { MonoLabel } from "@/components/ui/MonoLabel";
import type { WarmPathData } from "@/lib/types";

export function WarmPath({ path }: { path: WarmPathData }) {
  return (
    <section className="warm-path" aria-label={`Warm path through ${path.display_name}`}>
      <div className="warm-action">
        <Avatar name={path.display_name} size={36} path />
        <div>
          <MonoLabel>Your warm path</MonoLabel>
          <div><strong>{path.display_name}</strong>{path.current_role ? ` · ${path.current_role}` : ""}</div>
        </div>
        {path.confidence_band && <Badge tone="accent">{path.confidence_band} confidence</Badge>}
      </div>
      <div className="path-nodes" aria-label={path.path.join(" to ")}>
        {path.path.map((node, index) => (
          <span key={`${node}-${index}`} className="contents">
            {index > 0 && <span className="path-edge" aria-hidden="true" />}
            <span className="path-node">{node}</span>
          </span>
        ))}
      </div>
      {path.relevance_reason && <p className="path-reason">{path.relevance_reason}</p>}
      {path.suggested_action && <p className="path-reason"><strong>Recommended:</strong> {path.suggested_action}</p>}
    </section>
  );
}
