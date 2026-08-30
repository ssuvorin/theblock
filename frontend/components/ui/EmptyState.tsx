import type { HTMLAttributes, ReactNode } from "react";

interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  action?: ReactNode;
}

export function EmptyState({ title, action, children, ...props }: EmptyStateProps) {
  return (
    <div className="empty-state" {...props}>
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
