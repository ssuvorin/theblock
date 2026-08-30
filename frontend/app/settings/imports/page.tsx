"use client";

import { FormEvent, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { SettingsTabs } from "@/components/SettingsTabs";
import { Badge, Button, MonoLabel } from "@/components/ui";
import { apiMessage, fetchApi } from "@/lib/api";

export default function ImportsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<unknown>(null);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setReport(null);
    const body = new FormData();
    body.set("archive", file);
    try {
      setReport(await fetchApi("/api/imports/linkedin", { method: "POST", body }));
    } catch (requestError) {
      setError(apiMessage(requestError));
    } finally {
      setBusy(false);
    }
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
          <input id="archive-file" className="file-input" type="file" accept=".zip,application/zip" onChange={(event) => setFile(event.target.files?.[0] || null)} required />
          <div className="form-footer">
            <span className="form-help">{file ? file.name : "No archive selected"}</span>
            <Button type="submit" variant="primary" disabled={busy || !file}>{busy ? "Importing" : "Import archive"}</Button>
          </div>
        </form>
        {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
        {report != null && <pre className="card card-body import-report" aria-label="Import report">{JSON.stringify(report, null, 2)}</pre>}
      </div>
    </AppShell>
  );
}
