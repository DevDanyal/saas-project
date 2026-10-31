"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { useUser } from "@/lib/user-context";
import { SyncBar } from "@/components/sync-bar";
import { ConnectGmail } from "@/components/connect-gmail";

const NAV = [
  { href: "/", label: "Inbox" },
  { href: "/actions", label: "Action Items" },
  { href: "/digest", label: "Daily Digest" },
  { href: "/alerts", label: "Alerts" },
  { href: "/billing", label: "Billing" },
  { href: "/teams", label: "Teams" },
  { href: "/reports", label: "Reports" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { users, activeId, setActiveId, connectGmail, unreadCount } = useUser();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          Smart <em>Inbox</em>
        </div>
        <nav className="nav">
          {NAV.map((n) => {
            const active =
              n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={active ? "active" : ""}>
                {n.label}
                {n.href === "/alerts" && unreadCount > 0 && (
                  <span className="nav-count">{unreadCount}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="grow" />
        {users.length > 0 && (
          <div className="user-switch">
            <select
              value={activeId ?? ""}
              onChange={(e) => setActiveId(e.target.value)}
              aria-label="Switch agent account"
            >
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                </option>
              ))}
            </select>
          </div>
        )}
        <button
          className="btn"
          onClick={() => connectGmail()}
          style={{ width: "100%", justifyContent: "center" }}
        >
          + Connect Gmail
        </button>
      </aside>
      <main className="content">
        <Suspense fallback={null}>
          <ConnectGmail />
        </Suspense>
        <SyncBar />
        {children}
      </main>
    </div>
  );
}