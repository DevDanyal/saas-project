"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { Mail } from "lucide-react";

import { useUser } from "@/lib/user-context";
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
  const { user, authChecked, logout, unreadCount } = useUser();

  if (!authChecked) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--paper)]">
        <div className="flex items-center gap-3 text-[13px] text-[var(--muted)]">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--gold)]" />
          Loading workspace…
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  const initial = (user.email?.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();

  return (
    <div className="app">
      <header className="topbar">
        <Link href="/" className="topbar-brand">
          <Mail size={18} />
          Smart Inbox
        </Link>
        <nav className="topbar-tabs" aria-label="Primary">
          {NAV.map((n) => {
            const active =
              n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`topbar-tab ${active ? "active" : ""}`}
              >
                {n.label}
                {n.href === "/alerts" && unreadCount > 0 && (
                  <span className="nav-count">{unreadCount}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="topbar-account">
          <span className="avatar">{initial}</span>
          <span className="account-email" title={user.email}>{user.email}</span>
          <button className="btn btn-outline btn-sm" onClick={() => void logout()}>
            Sign out
          </button>
        </div>
      </header>
      <main className="main">
        <Suspense fallback={null}>
          <ConnectGmail />
        </Suspense>
        {children}
      </main>
    </div>
  );
}
