"use client";

import { useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { RelationshipGraph } from "@/components/RelationshipGraph";
import { Badge, Button, MonoLabel } from "@/components/ui";
import { fetchApi } from "@/lib/api";
import { useApiData } from "@/lib/useApi";
import type { OpportunitiesResponse } from "@/lib/types";

const loadPaths = () => fetchApi<OpportunitiesResponse>("/api/opportunities?limit=50&page=1");

export default function GraphPage() {
  const { data, loaded, error, reload } = useApiData(loadPaths);
  const paths = useMemo(() => (data?.opportunities || []).flatMap((opportunity) => opportunity.warm_paths || []), [data]);

  return (
    <AppShell title="Graph" topbarMeta={<Badge tone="accent">{loaded ? `${paths.length} supported paths` : "Reading paths"}</Badge>}>
      <div className="page">
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Relationship graph · evidence-backed edges only</MonoLabel>
            <h1 className="page-title">See the credible route into an opportunity.</h1>
            <p className="page-subtitle">Node size follows relationship strength when that score is available. Orange rings and dashed edges mark the active introduction paths.</p>
          </div>
          <Button variant="primary" onClick={reload}>Refresh graph</Button>
        </header>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        {!loaded ? <div className="loading-panel">Reconstructing supported paths</div> : <RelationshipGraph paths={paths} />}
      </div>
    </AppShell>
  );
}
