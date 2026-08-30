"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { apiMessage, fetchApi } from "@/lib/api";
import type { ScheduleMeetingResponse } from "@/lib/types";

const DEFAULT_MINUTES = 30;

type FieldIds = ReturnType<typeof useFieldIds>;

/**
 * Creates one Google Meet event on an explicit submit. Nothing here fires automatically.
 *
 * Validation is native (`required`, `datetime-local`, constraints) so the browser reports
 * problems in the user's own language. The submit button is disabled only while a valid
 * submission is in flight — to prevent a duplicate invite, not to block the attempt.
 */
export function ScheduleMeetingForm({ enabled, reason }: { enabled: boolean; reason?: string }) {
  const ids = useFieldIds();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ScheduleMeetingResponse | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Captured before awaiting: `currentTarget` is cleared once the handler returns.
    const form = event.currentTarget;
    setSending(true);
    setError("");
    try {
      const response = await fetchApi<ScheduleMeetingResponse>("/api/meetings", {
        method: "POST",
        body: payload(new FormData(form)),
      });
      setResult(response);
      form.reset();
    } catch (requestError) {
      setError(apiMessage(requestError));
    } finally {
      setSending(false);
    }
  }

  if (!enabled) return <DisabledCard reason={reason} />;

  return (
    <Card
      title="Schedule a Google Meet"
      meta={<Badge tone="accent">creates a calendar event</Badge>}
    >
      <form className="login-form" onSubmit={submit}>
        <MeetingFields ids={ids} />
        <div className="form-footer">
          <Button variant="accent" type="submit" disabled={sending}>
            {sending ? "Creating" : "Create meeting and invite"}
          </Button>
          <span className="form-help">
            One event per submit. Nothing is scheduled automatically.
          </span>
        </div>
      </form>
      <div aria-live="polite">
        {error && (
          <div className="degraded-banner" role="alert">
            <span className="banner-mark">×</span>
            {error}
          </div>
        )}
        {result && <MeetingResult result={result} />}
      </div>
    </Card>
  );
}

function DisabledCard({ reason }: { reason?: string }) {
  return (
    <Card title="Schedule a Google Meet" meta={<Badge>disabled</Badge>}>
      <p className="prose-tone">
        {reason ??
          "Meeting scheduling is off. It needs GOOGLE_MEETING_SCHEDULING=true and a Google " +
            "connection consented to the calendar write scope."}
      </p>
    </Card>
  );
}

function MeetingFields({ ids }: { ids: FieldIds }) {
  return (
    <fieldset className="meeting-fieldset">
      <legend className="field-label">Meeting details</legend>
      <div className="field-group">
        <label className="field-label" htmlFor={ids.title}>
          Title
        </label>
        <input
          className="field"
          id={ids.title}
          name="title"
          type="text"
          required
          maxLength={200}
          placeholder="Intro call"
        />
      </div>
      <div className="field-group">
        <label className="field-label" htmlFor={ids.starts}>
          Starts at
        </label>
        <input
          className="field"
          id={ids.starts}
          name="starts_at"
          type="datetime-local"
          required
        />
      </div>
      <div className="field-group">
        <label className="field-label" htmlFor={ids.duration}>
          Duration in minutes
        </label>
        <input
          className="field"
          id={ids.duration}
          name="duration_minutes"
          type="number"
          min={5}
          max={480}
          defaultValue={DEFAULT_MINUTES}
        />
      </div>
      <GuestField ids={ids} />
    </fieldset>
  );
}

function GuestField({ ids }: { ids: FieldIds }) {
  return (
    <div className="field-group">
      <label className="field-label" htmlFor={ids.guests}>
        Guest emails
      </label>
      <input
        className="field"
        id={ids.guests}
        name="guest_emails"
        type="text"
        required
        autoComplete="email"
        inputMode="email"
        placeholder="priya@example.com, tom@example.com"
        aria-describedby={ids.guestHelp}
      />
      <span className="form-help" id={ids.guestHelp}>
        Comma separated. Each address receives a calendar invite.
      </span>
    </div>
  );
}

function MeetingResult({ result }: { result: ScheduleMeetingResponse }) {
  const { meeting, collabute } = result;
  return (
    <dl className="definition-list meeting-result">
      <dt>Meet link</dt>
      <dd>
        {meeting.meet_url ? (
          <a href={meeting.meet_url} rel="noreferrer noopener" target="_blank">
            {meeting.meet_url}
          </a>
        ) : (
          `Google is still creating the conference (${meeting.conference_status}).`
        )}
      </dd>
      <dt>Invites</dt>
      <dd>
        {meeting.invites_sent
          ? meeting.guests.join(", ")
          : "Not sent — you chose not to notify the guests."}
      </dd>
      <dt>Notetaker</dt>
      <dd>{collabute.notetaker_attached ? "Attached" : collabute.reason}</dd>
    </dl>
  );
}

function useFieldIds() {
  const prefix = useId();
  return {
    title: `${prefix}-title`,
    starts: `${prefix}-starts`,
    duration: `${prefix}-duration`,
    guests: `${prefix}-guests`,
    guestHelp: `${prefix}-guest-help`,
  };
}

function payload(form: FormData): Record<string, unknown> {
  const duration = Number(form.get("duration_minutes"));
  return {
    title: String(form.get("title") ?? ""),
    starts_at: new Date(String(form.get("starts_at"))).toISOString(),
    duration_minutes: Number.isFinite(duration) && duration > 0 ? duration : DEFAULT_MINUTES,
    guest_emails: String(form.get("guest_emails") ?? "")
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean),
  };
}
