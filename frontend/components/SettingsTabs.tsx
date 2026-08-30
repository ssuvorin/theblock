"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "@/lib/cx";

const tabs = [
  ["/settings/connections", "Connected accounts"],
  ["/settings/imports", "Data imports"],
  ["/settings/data", "Data & privacy"],
] as const;

export function SettingsTabs() {
  const pathname = usePathname();
  return (
    <nav className="settings-tabs" aria-label="Settings sections">
      {tabs.map(([href, label]) => (
        <Link key={href} href={href} className={cx("settings-tab", pathname === href && "settings-tab-active")}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
