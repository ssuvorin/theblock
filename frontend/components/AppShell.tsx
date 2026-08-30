"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, ReactNode, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClassName, Button } from "@/components/ui/Button";
import { cx } from "@/lib/cx";
import { useOwner } from "@/lib/useOwner";

const workspaceLinks = [
  { index: "01", label: "Ask", href: "/query" },
  { index: "02", label: "People", href: "/people" },
  { index: "03", label: "Graph", href: "/graph" },
  { index: "04", label: "Signals", href: "/signals" },
];

const systemLinks = [
  { index: "05", label: "First run", href: "/onboarding" },
  { index: "06", label: "Sources", href: "/settings/connections" },
  { index: "07", label: "Imports", href: "/settings/imports" },
  { index: "08", label: "Data", href: "/settings/data" },
];

interface AppShellProps {
  title: string;
  children: ReactNode;
  topbarMeta?: ReactNode;
}

function NavItem({ index, label, href, active }: (typeof workspaceLinks)[number] & { active: boolean }) {
  return (
    <Link className={cx("nav-link", active && "nav-link-active")} href={href} aria-current={active ? "page" : undefined}>
      <span className="nav-index">{index}</span>
      <span className="nav-link-label">{label}</span>
    </Link>
  );
}

export function AppShell({ title, children, topbarMeta }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const owner = useOwner();
  const [query, setQuery] = useState("");
  const [light, setLight] = useState(false);

  function isActive(href: string) {
    return href === "/query" ? pathname === href : pathname.startsWith(href);
  }

  function search(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (value) router.push(`/people?q=${encodeURIComponent(value)}`);
  }

  function toggleTheme() {
    const nextLight = !light;
    setLight(nextLight);
    document.documentElement.dataset.theme = nextLight ? "light" : "";
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link className="brand-lockup" href="/query" aria-label="Career Brain home">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Career Brain</span>
        </Link>
        <div className="nav-section-label">Workspace</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {workspaceLinks.map((link) => <NavItem key={link.href} {...link} active={isActive(link.href)} />)}
        </nav>
        <div className="settings-nav-items">
          <div className="nav-section-label">System</div>
          <nav aria-label="System navigation">
            {systemLinks.map((link) => <NavItem key={link.href} {...link} active={isActive(link.href)} />)}
          </nav>
        </div>
        <div className="sidebar-account">
          <Avatar name={owner?.display_name ?? "Owner"} size={32} />
          <div className="account-copy">
            <span className="account-name">{owner?.display_name ?? "—"}</span>
            <span className="account-email">{owner?.email ?? "owner workspace"}</span>
          </div>
        </div>
      </aside>
      <div className="shell-content">
        <header className="app-topbar">
          <span className="topbar-title">{title}</span>
          {topbarMeta}
          <form className="global-search" role="search" onSubmit={search}>
            <label className="sr-only" htmlFor="global-search">Search people</label>
            <input id="global-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search people, companies, documents" />
          </form>
          <div className="topbar-actions">
            <Button size="small" variant="ghost" onClick={toggleTheme} aria-pressed={light}>{light ? "Dark" : "Light"}</Button>
            <Link href="/query" className={buttonClassName("primary", "small")}>New ask</Link>
          </div>
        </header>
        <main id="main-content">{children}</main>
      </div>
    </div>
  );
}
