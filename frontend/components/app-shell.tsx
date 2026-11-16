"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { useUser } from "@/lib/user-context";
import { SyncBar } from "@/components/sync-bar";
import { ConnectGmail } from "@/components/connect-gmail";
import { AuthScreen } from "@/components/auth/auth-screen";

const NAV = [
  { href: "/", label: "Inbox" },
  { href: "/actions", label: "Action Items" },
  { href: "/digest", label: "Daily Digest" },
  { href: "/alerts", label: "Alerts" },
  { href: "/billing", label: "Billing" },
  { href: "/teams", label: "Teams" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, authChecked, connectGmail, logout, unreadCount } = useUser();

  if (!authChecked) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--paper)]">
        <div className="flex items-center gap-3 text-[13px] text-[var(--muted)]">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--gold)]" />
          Loading workspace...
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          Smart <em>Inbox</em>
        </div>
        <div className="sidebar-eyebrow">Agent workspace</div>
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
        <div className="user-switch">
          <span title={user.email}>{user.email}</span>
        </div>
        {!user.gmail_connected && (
          <button
            className="btn"
            onClick={() => void connectGmail()}
            style={{ width: "100%", justifyContent: "center" }}
          >
            + Connect Gmail
          </button>
        )}
        <button
          className="btn"
          onClick={() => void logout()}
          style={{ width: "100%", justifyContent: "center" }}
        >
          Sign out
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
