"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import {
  Bell, CheckSquare, CreditCard, FileBarChart, Home, Inbox, LogOut,
  Menu, Settings, Sparkles, Users, X,
} from "lucide-react";
import { useUser } from "@/lib/user-context";
import { ConnectGmail } from "@/components/connect-gmail";
import { AuthScreen } from "@/components/auth/auth-screen";

const NAV = [
  { href: "/", label: "Inbox", icon: Inbox },
  { href: "/actions", label: "Action Items", icon: CheckSquare },
  { href: "/digest", label: "Daily Digest", icon: Sparkles },
  { href: "/alerts", label: "Alerts", icon: Bell, badgeKey: "alerts" as const },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/reports", label: "Reports", icon: FileBarChart },
  { href: "/settings", label: "Settings", icon: Settings },
];

const MOBILE_TABS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/", label: "Inbox", icon: Inbox, exact: true },
  { href: "/actions", label: "Actions", icon: CheckSquare },
  { href: "/alerts", label: "Alerts", icon: Bell, badgeKey: "alerts" as const },
  { href: "/settings", label: "More", icon: Settings },
];

function titleFor(pathname: string) {
  if (pathname === "/") return "Smart Inbox";
  if (pathname.startsWith("/thread")) return "Conversation";
  const item = NAV.find((n) => n.href !== "/" && pathname.startsWith(n.href));
  return item?.label ?? "Smart Inbox";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, authChecked, unreadCount, logout, syncInbox, busy } = useUser();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const activeHref = useMemo(() => {
    if (pathname === "/") return "/";
    const found = NAV.find((n) => n.href !== "/" && pathname.startsWith(n.href));
    return found?.href ?? "/";
  }, [pathname]);

  if (!authChecked) {
    return (
      <div className="app-bg" style={{ minHeight: "100dvh", display: "grid", placeItems: "center" }}>
        <div className="card card-pad row" style={{ gap: 10 }}>
          <span className="spin" /> <span className="sub">Loading your workspace…</span>
        </div>
      </div>
    );
  }
  if (!user) return <AuthScreen />;

  const initial = (user.email?.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();

  async function handleSync() {
    setSyncMsg(null);
    try {
      const s = await syncInbox();
      setSyncMsg(`Synced ${s.emails_added} new emails`);
    } catch {
      setSyncMsg("Sync failed");
    }
    setTimeout(() => setSyncMsg(null), 2500);
  }

  return (
    <div className="app-bg shell">
      <aside className="sidebar" aria-label="Primary">
        <Link href="/" className="brand">
          <span className="brand-mark"><Inbox size={16} /></span>
          <span>Smart Inbox</span>
        </Link>
        <nav className="nav-group">
          {NAV.map((n) => {
            const Icon = n.icon;
            const active = n.href === "/" ? activeHref === "/" && !pathname.startsWith("/thread") || pathname.startsWith("/thread") ? n.href === "/" : false : activeHref === n.href;
            const isActive = n.href === "/" ? (pathname === "/" || pathname.startsWith("/thread")) : pathname.startsWith(n.href);
            return (
              <Link key={n.href + n.label} href={n.href} className={`nav-item ${isActive ? "active" : ""}`}>
                <Icon size={16} /> <span>{n.label}</span>
                {n.badgeKey === "alerts" && unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="user-pill">
            <span className="avatar">{initial}</span>
            <div className="user-meta">
              <div className="user-email">{user.email}</div>
              <div className="user-sub">{user.gmail_connected ? "Gmail connected" : "Gmail not connected"}</div>
            </div>
          </div>
          <button className="btn ghost sm" onClick={() => void logout()} style={{ justifyContent: "flex-start" }}>
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="row">
            <button className="btn icon-btn ghost" onClick={() => setDrawerOpen(true)} aria-label="Open menu" style={{ display: "none" }} id="mobile-menu-btn" />
            <div>
              <div className="topbar-title">{titleFor(pathname)}</div>
              <div className="topbar-sub">Triage, reply, and stay ahead of every client.</div>
            </div>
          </div>
          <div className="topbar-actions">
            <button className="btn sm" onClick={() => void handleSync()} disabled={busy || !user.gmail_connected}>
              {busy ? <span className="spin" /> : null} Sync
            </button>
            <span className="avatar" title={user.email}>{initial}</span>
          </div>
        </header>

        <main className="content">
          <Suspense fallback={null}><ConnectGmail /></Suspense>
          {syncMsg && <div className="notice-banner" style={{ marginBottom: 12 }}>{syncMsg}</div>}
          {children}
        </main>
      </div>

      {drawerOpen && (
        <>
          <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)} />
          <aside className="drawer" aria-label="Menu">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="brand" style={{ padding: 0 }}><span className="brand-mark"><Inbox size={16} /></span>Smart Inbox</div>
              <button className="btn icon-btn ghost" onClick={() => setDrawerOpen(false)} aria-label="Close"><X size={16} /></button>
            </div>
            <nav className="nav-group">
              {NAV.map((n) => {
                const Icon = n.icon;
                const isActive = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
                return (
                  <Link key={n.href} href={n.href} onClick={() => setDrawerOpen(false)} className={`nav-item ${isActive ? "active" : ""}`}>
                    <Icon size={16} /> {n.label}
                    {n.badgeKey === "alerts" && unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
                  </Link>
                );
              })}
            </nav>
            <div className="sidebar-foot" style={{ borderTop: "1px solid var(--border)", marginTop: "auto" }}>
              <div className="user-pill"><span className="avatar">{initial}</span><div className="user-meta"><div className="user-email">{user.email}</div></div></div>
              <button className="btn sm" onClick={() => { void handleSync(); }} disabled={busy}>Sync inbox</button>
              <button className="btn ghost sm" onClick={() => void logout()}><LogOut size={14} /> Sign out</button>
            </div>
          </aside>
        </>
      )}

      <nav className="mobile-tabs" aria-label="Primary">
        {MOBILE_TABS.map((t, i) => {
          const Icon = t.icon;
          const isActive = t.href === "/alerts" ? pathname.startsWith("/alerts")
            : t.href === "/actions" ? pathname.startsWith("/actions")
            : t.href === "/settings" ? (pathname.startsWith("/settings") || pathname.startsWith("/billing") || pathname.startsWith("/teams") || pathname.startsWith("/reports"))
            : i === 1 ? (pathname === "/" || pathname.startsWith("/thread"))
            : i === 0 ? pathname === "/" : false;
          return (
            <Link key={t.label} href={t.href} className={`mobile-tab ${isActive ? "active" : ""}`} onClick={() => { if (t.label === "More") setDrawerOpen(true); }}>
              <span style={{ position: "relative", display: "inline-flex" }}>
                <Icon size={18} />
                {t.badgeKey === "alerts" && unreadCount > 0 && <span style={{ position: "absolute", top: -4, right: -6, width: 8, height: 8, borderRadius: 99, background: "var(--hot)" }} />}
              </span>
              <span>{t.label}</span>
            </Link>
          );
        })}
      </nav>

      {syncMsg && <div className="toast">{syncMsg}</div>}
    </div>
  );
}
