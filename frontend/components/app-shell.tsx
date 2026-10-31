"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";

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

function LoginPanel() {
  const { connectGmail, error } = useUser();
  const [busy, setBusy] = useState(false);

  async function signIn() {
    setBusy(true);
    try {
      await connectGmail();
    } catch {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <main className="content" style={{ margin: "0 auto", maxWidth: 460 }}>
        <div className="empty" style={{ marginTop: 80 }}>
          <h2>Smart Inbox</h2>
          <p>
            Sign in with Google to connect your inbox. We read and summarize your
            email so you can approve or ignore each thread. Nothing is sent
            without your say.
          </p>
          {error && <div className="error-banner">{error}</div>}
          <button
            className="btn primary"
            onClick={signIn}
            disabled={busy}
            style={{ marginTop: 10 }}
          >
            {busy && <span className="spin" />} Continue with Google
          </button>
        </div>
      </main>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, authChecked, connectGmail, logout, unreadCount } = useUser();

  if (!authChecked) {
    return (
      <div className="shell">
        <main className="content">
          <div className="empty">Loading…</div>
        </main>
      </div>
    );
  }

  if (!user) {
    return <LoginPanel />;
  }

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
