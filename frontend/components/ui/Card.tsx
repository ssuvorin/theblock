import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/cx";

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  meta?: ReactNode;
}

export function Card({ title, meta, className, children, ...props }: CardProps) {
  return (
    <section className={cx("card", className)} {...props}>
      {(title || meta) && (
        <header className="card-header">
          {typeof title === "string" ? <h2 className="card-title">{title}</h2> : title}
          {meta}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
