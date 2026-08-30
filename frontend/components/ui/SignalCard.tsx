import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export function SignalCard({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <article className={cx("signal-card", className)} {...props} />;
}
