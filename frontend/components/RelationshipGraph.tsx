import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { MonoLabel } from "@/components/ui/MonoLabel";
import type { WarmPathData } from "@/lib/types";

type GraphNode = { name: string; x: number; y: number; size: number; path: boolean; you: boolean };
type GraphEdge = { from: GraphNode; to: GraphNode; path: boolean };

const positions = [
  [18, 50], [43, 24], [43, 50], [43, 76], [75, 28], [76, 51], [75, 74], [61, 14], [62, 87],
];

function buildGraph(paths: WarmPathData[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const names = ["You", ...new Set(paths.flatMap((item) => item.path).filter((name) => name.toLowerCase() !== "you"))];
  const pathNames = new Set(paths.flatMap((item) => item.path).map((name) => name.toLowerCase()));
  const nodes = names.slice(0, positions.length).map((name, index) => {
    const personPath = paths.find((item) => item.display_name.toLowerCase() === name.toLowerCase());
    const score = personPath?.strength_score;
    const size = name === "You" ? 68 : score == null ? 48 : Math.round(40 + Math.max(0, Math.min(1, score)) * 20);
    return { name, x: positions[index][0], y: positions[index][1], size, path: pathNames.has(name.toLowerCase()), you: name === "You" };
  });
  const lookup = new Map(nodes.map((node) => [node.name.toLowerCase(), node]));
  const edges: GraphEdge[] = [];
  paths.forEach((item) => item.path.slice(1).forEach((name, index) => {
    const from = lookup.get(item.path[index].toLowerCase());
    const to = lookup.get(name.toLowerCase());
    if (from && to && !edges.some((edge) => edge.from === from && edge.to === to)) edges.push({ from, to, path: true });
  }));
  return { nodes, edges };
}

export function RelationshipGraph({ paths }: { paths: WarmPathData[] }) {
  if (!paths.length) return <EmptyState title="No supported path graph">The API returned no evidence-backed warm paths for this view.</EmptyState>;
  const graph = buildGraph(paths);
  return (
    <section className="graph-layout" aria-label="Evidence-backed relationship graph">
      <div className="relationship-graph">
        <svg className="graph-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {graph.edges.map((edge, index) => (
            <line key={index} x1={edge.from.x} y1={edge.from.y} x2={edge.to.x} y2={edge.to.y} className={edge.path ? "graph-edge-path" : "graph-edge"} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        {graph.nodes.map((node) => (
          <div key={node.name} className={`graph-node ${node.path ? "graph-node-path" : ""} ${node.you ? "graph-node-you" : ""}`} style={{ left: `${node.x}%`, top: `${node.y}%` }}>
            <Avatar name={node.name === "You" ? "Alex Ivanov" : node.name} size={node.size} path={node.path && !node.you} you={node.you} />
            <span>{node.name.toUpperCase()}{node.you ? " (YOU)" : ""}</span>
          </div>
        ))}
        <div className="graph-legend">
          <div className="legend-row"><span className="legend-line" />relationship evidence</div>
          <div className="legend-row"><span className="legend-line legend-path" />path to opportunity</div>
        </div>
      </div>
      <aside className="graph-aside" aria-label="Warm paths">
        <div className="card-header"><h2 className="card-title">Supported paths</h2></div>
        {paths.map((path, index) => (
          <div className="graph-path-card" key={`${path.person_id}-${index}`}>
            <MonoLabel>Path {index + 1} · {path.confidence_band || "confidence unavailable"}</MonoLabel>
            <p>{path.path.join(" → ")}</p>
          </div>
        ))}
      </aside>
    </section>
  );
}
