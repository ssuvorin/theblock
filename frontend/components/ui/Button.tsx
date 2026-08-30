import type { ButtonHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "accent";
export type ButtonSize = "small" | "medium" | "large";

export function buttonClassName(
  variant: ButtonVariant = "secondary",
  size: ButtonSize = "medium",
  full = false,
): string {
  return cx(
    "button",
    `button-${variant}`,
    size !== "medium" && `button-${size}`,
    full && "button-full",
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  full?: boolean;
}

export function Button({
  variant = "secondary",
  size = "medium",
  full = false,
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(buttonClassName(variant, size, full), className)}
      {...props}
    />
  );
}
