"use client";

import { AppShell } from "@/components/AppShell";
import { OnboardingSteps } from "@/components/OnboardingSteps";
import { Badge, MonoLabel } from "@/components/ui";
import { fetchApi } from "@/lib/api";
import { useApiData } from "@/lib/useApi";
import type { PeopleResponse } from "@/lib/types";

const loadPeopleTotal = () => fetchApi<PeopleResponse>("/api/people?page=1&limit=1");

export default function OnboardingPage() {
  const { data, loaded, error } = useApiData(loadPeopleTotal);
  const total = typeof data?.total === "number" ? data.total : undefined;

  return (
    <AppShell title="First run" topbarMeta={<Badge tone="strong">1 required step · 2 not wired</Badge>}>
      <div className="page page-narrow">
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>First run · setup in order</MonoLabel>
            <h1 className="page-title">Give the graph something real to read.</h1>
            <p className="page-subtitle">Only the LinkedIn archive import writes data today. The other two steps are listed so you can see what is not connected yet, and the required step is checked against your graph rather than remembered locally.</p>
          </div>
        </header>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        <OnboardingSteps loaded={loaded} total={total} />
      </div>
    </AppShell>
  );
}
