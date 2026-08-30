"use client";

import { FormEvent, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ImportReport } from "@/components/ImportReport";
import { SettingsTabs } from "@/components/SettingsTabs";
import { Badge, Button, MonoLabel } from "@/components/ui";
import { apiMessage, fetchApi } from "@/lib/api";
import type { LinkedInImportReport } from "@/lib/types";

type ImportMode = "validate" | "import";

function useArchiveImport() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<ImportMode | "">("");
  const [error, setError] = useState("");
  const [report, setReport] = useState<LinkedInImportReport | null>(null);

  async function send(mode: ImportMode) {
    if (!file || busy) return;
    setBusy(mode);
    setError("");
    setReport(null);
    const body = new FormData();
    body.set("archive", file);
    const path = mode === "validate" ? "/api/imports/linkedin?dry_run=true" : "/api/imports/linkedin";
    try {
      setReport(await fetchApi<LinkedInImportReport>(path, { method: "POST", body }));
    } catch (requestError) {
      setError(apiMessage(requestError));
    } finally {
      setBusy("");
    }
  }

  return { file, setFile, busy, error, report, send };
}

export default function ImportsPage() {
  const state = useArchiveImport();

  function upload(event: FormEvent) {
    event.preventDefault();
    void state.send("import");
  }

  return (
    <AppShell title="Data imports" topbarMeta={<Badge tone="strong">File-based · no scraping</Badge>}>
      <div className="page page-narrow">
        <SettingsTabs />
        <header className="page-header">
          <div className="page-heading-block">
            <MonoLabel>Relationship archive</MonoLabel>
            <h1 className="page-title">Import the conversations you choose to export.</h1>
            <p className="page-subtitle">Career Brain never asks for a LinkedIn password. Upload an archive file; messages are parsed with source provenance and duplicate-safe identifiers.</p>
          </div>
        </header>
        <form className="drop-zone" onSubmit={upload}>
          <MonoLabel>LinkedIn data export · ZIP</MonoLabel>
          <p className="prose-tone">The importer uses message reciprocity as relationship evidence. Invitations alone do not create people.</p>
          <label className="field-label" htmlFor="archive-file">Choose archive</label>
          <input id="archive-file" className="file-input" type="file" accept=".zip,application/zip" onChange={(event) => state.setFile(event.target.files?.[0] || null)} required />
          <div className="form-footer">
            <span className="form-help">{state.file ? state.file.name : "No archive selected"}</span>
            <div className="import-actions">
              <Button variant="secondary" onClick={() => state.send("validate")} disabled={Boolean(state.busy) || !state.file}>{state.busy === "validate" ? "Validating" : "Validate only"}</Button>
              <Button type="submit" variant="primary" disabled={Boolean(state.busy) || !state.file}>{state.busy === "import" ? "Importing" : "Import archive"}</Button>
            </div>
          </div>
          <p className="import-note">Validate only calls the same endpoint with dry_run=true: the archive is parsed and counted, nothing is written.</p>
        </form>
        {state.error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{state.error}</div>}
        {state.report && <ImportReport report={state.report} />}
      </div>
    </AppShell>
  );
}
