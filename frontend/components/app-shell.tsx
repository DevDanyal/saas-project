"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";
import { Mail, Menu, X, Home, Inbox, PenSquare, Bell, Settings } from "lucide-react";
import { useUser } from "@/lib/user-context";
import { ConnectGmail } from "@/components/connect-gmail";
import { AuthScreen } from "@/components/auth/auth-screen";

const NAV = [
  { href: "/", label: "Inbox" },
  { href: "/actions", label: "Action Items" },
  { href: "/digest", label: "Daily Digest" },
  { href: "/alerts", label: "Alerts" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, authChecked, unreadCount } = useUser();
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!authChecked) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[#EEF2F9]">
        <div className="flex items-center gap-3 text-[13px] text-slate-500">
          <span className="spin !w-4 !h-4 border-slate-300 border-t-indigo-600" />
          Loading workspace…
        </div>
      </div>
    );
  }
  if (!user) return <AuthScreen />;

  const initial = (user.email?.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="app-shell min-h-screen bg-[#EEF2F9]">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-4 px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <button className="lg:hidden inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700" onClick={() => setDrawerOpen(true)} aria-label="Open menu">
              <Menu size={18} />
            </button>
            <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white"><Mail size={16} /></span>
              <span className="hidden sm:inline">Smart Inbox</span>
            </Link>
          </div>

          <nav className="hidden lg:flex items-center gap-1">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={`relative rounded-lg px-3 py-2 text-sm font-medium transition ${isActive(n.href) ? "text-indigo-700 bg-indigo-50" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"}`}>
                {n.label}
                {n.href === "/alerts" && unreadCount > 0 && <span className="ml-1.5 inline-flex min-w-[18px] items-center justify-center rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold text-white">{unreadCount}</span>}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/90 px-2 py-1 shadow-sm">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-[11px] font-semibold text-white">{initial}</span>
              <span className="max-w-[180px] truncate text-xs text-slate-600">{user.email}</span>
            </div>
            <span className="sm:hidden inline-flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">{initial}</span>
          </div>
        </div>
      </header>

      {drawerOpen && (
        <>
          <div className="drawer-backdrop lg:hidden" onClick={() => setDrawerOpen(false)} />
          <aside className="drawer lg:hidden">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold"><span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white"><Mail size={16} /></span>Smart Inbox</div>
              <button className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200" onClick={() => setDrawerOpen(false)} aria-label="Close menu"><X size={16} /></button>
            </div>
            <nav className="flex flex-col gap-1">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} onClick={() => setDrawerOpen(false)} className={`rounded-lg px-3 py-2 text-sm font-medium ${isActive(n.href) ? "bg-indigo-50 text-indigo-700" : "text-slate-700 hover:bg-slate-50"}`}>
                  {n.label}
                </Link>
              ))}
            </nav>
          </aside>
        </>
      )}

      <main className="mx-auto max-w-[1400px] px-4 pb-24 pt-5 lg:px-6 lg:pb-8">
        <Suspense fallback={null}><ConnectGmail /></Suspense>
        {children}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200/80 bg-white/95 backdrop-blur lg:hidden">
        <div className="mx-auto grid max-w-[520px] grid-cols-5 px-2 py-2 text-[11px] text-slate-500">
          <Link href="/" className={`flex flex-col items-center gap-1 py-1 ${pathname === "/" ? "text-indigo-600" : ""}`}><Home size={18} /><span>Home</span></Link>
          <Link href="/" className={`flex flex-col items-center gap-1 py-1 ${pathname === "/" ? "text-indigo-600" : ""}`}><Inbox size={18} /><span>Mail</span></Link>
          <Link href="/actions" className="flex flex-col items-center gap-1 py-1"><PenSquare size={18} /><span>Compose</span></Link>
          <Link href="/alerts" className={`relative flex flex-col items-center gap-1 py-1 ${isActive("/alerts") ? "text-indigo-600" : ""}`}><Bell size={18} /><span>Alerts</span>{unreadCount > 0 && <span className="absolute right-4 top-0 h-2 w-2 rounded-full bg-rose-500" />}</Link>
          <Link href="/settings" className={`flex flex-col items-center gap-1 py-1 ${isActive("/settings") ? "text-indigo-600" : ""}`}><Settings size={18} /><span>Settings</span></Link>
        </div>
      </nav>
    </div>
  );
}
