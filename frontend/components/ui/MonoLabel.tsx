import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export function MonoLabel({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cx("mono-label", className)} {...props} />;
}
