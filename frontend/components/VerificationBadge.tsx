import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { VerificationStatus } from "@/lib/types";

const statusContent: Record<VerificationStatus, { label: string; tone: BadgeTone; className: string }> = {
  verified_open_role: { label: "Verified open role", tone: "accent", className: "verification-verified" },
  hiring_signal: { label: "Hiring signal · no open role verified", tone: "positive", className: "verification-signal" },
  unverified: { label: "Unverified", tone: "neutral", className: "verification-unverified" },
  stale: { label: "Stale source", tone: "error", className: "verification-stale" },
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const content = statusContent[status];
  return <Badge tone={content.tone} className={`verification-badge ${content.className}`}>{content.label}</Badge>;
}
