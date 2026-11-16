"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, CalendarClock, Flame, Inbox, Sparkles } from "lucide-react";
import { get } from "@/lib/api";
import type { Digest } from "@/lib/types";
import { useUser } from "@/lib/user-context";

function Section({ title, icon, items, href }: { title: string; icon: React.ReactNode; items: string[]; href?: string }) {
  return (
    <div className="card card-pad">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <div className="row" style={{ gap: 8 }}>{icon}<div className="label" style={{ margin: 0 }}>{title}</div></div>
        {href && <Link href={href} className="btn sm ghost">Open <ArrowRight size={14} /></Link>}
      </div>
      {!items || items.length === 0 ? (
        <div className="sub">Nothing here right now.</div>
      ) : (
        <ul className="section-list">{items.map((item, i) => <li key={i}>{item}</li>)}</ul>
      )}
    </div>
  );
}

export default function DigestPage() {
  const { activeId } = useUser();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try { const d = await get<Digest>(`/emails/digest/${activeId}`); if (!cancelled) setDigest(d); }
      catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [activeId]);

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Connect to generate your daily brief.</p></div>;
  if (loading) return <div className="card card-pad sub">Building your daily brief…</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const empty = !digest || (digest.threads_in_window === 0 && !digest.brief);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Daily Digest</h1>
          <div className="sub">A focused brief of hot leads, deadlines, and follow-ups from the last {digest?.window_hours ?? 24} hours.</div>
        </div>
        <Link href="/" className="btn sm"><Inbox size={14} /> Go to inbox</Link>
      </div>

      {digest && (
        <div className="grid-3">
          <div className="kpi"><div className="kpi-label">Threads in window</div><div className="kpi-value">{digest.threads_in_window}</div><div className="kpi-meta">Recent activity</div></div>
          <div className="kpi"><div className="kpi-label">Open actions</div><div className="kpi-value">{digest.actions_in_window}</div><div className="kpi-meta">Tasks to handle</div></div>
          <div className="kpi"><div className="kpi-label">Coverage</div><div className="kpi-value">{digest.window_hours}h</div><div className="kpi-meta">Digest window</div></div>
        </div>
      )}

      {empty ? (
        <div className="empty"><h2>No activity yet</h2><p>Sync and run AI on your inbox, then come back for a prioritized morning brief.</p></div>
      ) : (
        <>
          {digest?.brief && <div className="digest-brief"><div className="row" style={{ gap: 8, marginBottom: 8 }}><Sparkles size={16} color="var(--primary)" /><strong>Today’s brief</strong></div>{digest.brief}</div>}
          <div className="grid-2">
            <Section title="Hot leads" icon={<Flame size={16} color="var(--hot)" />} items={digest?.sections?.hot_leads ?? []} href="/" />
            <Section title="Closings & deadlines" icon={<CalendarClock size={16} color="var(--warn)" />} items={digest?.sections?.closings ?? []} href="/actions" />
            <Section title="Follow-ups needed" icon={<AlertTriangle size={16} color="var(--accent)" />} items={digest?.sections?.follow_ups ?? []} href="/actions" />
            <Section title="Other updates" icon={<Inbox size={16} color="var(--muted)" />} items={digest?.sections?.other ?? []} href="/" />
          </div>
        </>
      )}
    </div>
  );
}
