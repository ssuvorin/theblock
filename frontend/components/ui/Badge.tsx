import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export type BadgeTone = "neutral" | "accent" | "positive" | "error" | "strong";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return <span className={cx("badge", tone !== "neutral" && `badge-${tone}`, className)} {...props} />;
}
