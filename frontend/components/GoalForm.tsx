"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { MonoLabel } from "@/components/ui/MonoLabel";

const demoQuestion = "I’m looking for a Product Manager role at a crypto company in Dubai. Which relevant companies are hiring now? Who in my network could help me, and which warm paths should I follow first?";

interface GoalFormProps {
  onSubmit: (question: string) => Promise<void>;
  busy?: boolean;
}

export function GoalForm({ onSubmit, busy = false }: GoalFormProps) {
  const [question, setQuestion] = useState(demoQuestion);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (value) await onSubmit(value);
  }

  return (
    <form className="goal-form" onSubmit={submit}>
      <MonoLabel>Goal · current opportunities first, then your network</MonoLabel>
      <label className="sr-only" htmlFor="goal-question">Describe your career goal</label>
      <textarea
        id="goal-question"
        className="textarea goal-textarea"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder="Describe the role, industry, location, and help you need"
        required
      />
      <div className="form-footer">
        <span className="form-help">Public market evidence and private relationship evidence stay separate.</span>
        <Button type="submit" variant="primary" size="large" disabled={busy}>
          {busy ? "Searching" : "Find opportunities"}
        </Button>
      </div>
    </form>
  );
}
