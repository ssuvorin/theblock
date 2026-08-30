"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, MonoLabel } from "@/components/ui";
import { apiMessage, fetchApi } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchApi("/api/auth/session", { method: "POST", body: { email, password } });
      router.replace("/query");
      router.refresh();
    } catch (requestError) {
      setError(apiMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main-content" className="login-page">
      <section className="login-brand" aria-labelledby="login-brand-title">
        <h1 id="login-brand-title" className="login-wordmark">Career Brain</h1>
        <p className="login-claim">A job search engine knows who is hiring. Your relationship memory knows who can help you reach them.</p>
        <MonoLabel>Your network, working for your career.</MonoLabel>
      </section>
      <section className="login-panel" aria-labelledby="login-title">
        <form className="login-form" onSubmit={submit}>
          <div className="page-heading-block">
            <MonoLabel>Owner session</MonoLabel>
            <h2 id="login-title" className="page-title">Open your career memory.</h2>
            <p className="page-subtitle">Credentials establish a secure cookie session. They are not stored in this browser.</p>
          </div>
          <label className="field-group">
            <span className="field-label">Email</span>
            <input className="field" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label className="field-group">
            <span className="field-label">Password</span>
            <input className="field" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          {error && <div className="degraded-banner" role="alert"><span className="banner-mark">×</span>{error}</div>}
          <Button type="submit" variant="primary" size="large" full disabled={busy}>{busy ? "Opening session" : "Continue"}</Button>
        </form>
      </section>
    </main>
  );
}
