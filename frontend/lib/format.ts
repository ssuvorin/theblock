export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(date);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function sourceCode(source?: string): string {
  const codes: Record<string, string> = {
    gmail: "GM",
    email: "GM",
    whatsapp: "WA",
    calendar: "CAL",
    collabute: "CB",
    linkedin: "LI",
    document: "DOC",
  };
  return codes[source?.toLowerCase() ?? ""] ?? source?.slice(0, 3).toUpperCase() ?? "SRC";
}
