"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ArrowRight, CalendarClock, CheckCircle2, ChevronRight,
  Clock, Filter, Inbox, Search, Send, Sparkles, Zap,
} from "lucide-react";
import { get, patch } from "@/lib/api";
import {
  CategoryChip, FlagChip, ReplyStatusChip, ScorePill, formatTime,
} from "@/lib/format";
import type { InboxStats, ThreadDetail, ThreadSummary } from "@/lib/types";
import { useUser } from "@/lib/user-context";

type Queue = "home" | "urgent" | "needs_reply" | "hot_leads" | "waiting" | "all";

const QUEUES: { id: Queue; label: string; desc: string }[] = [
  { id: "home", label: "Home", desc: "Today’s priorities" },
  { id: "urgent", label: "Urgent", desc: "Needs attention now" },
  { id: "needs_reply", label: "Needs reply", desc: "Unanswered threads" },
  { id: "hot_leads", label: "Hot leads", desc: "High-intent buyers/sellers" },
  { id: "waiting", label: "Waiting", desc: "Replied, awaiting response" },
  { id: "all", label: "All mail", desc: "Everything" },
];

function sender(from: string | null | undefined) {
  const raw = (from || "Unknown").trim();
  if (raw.includes("<")) return raw.split("<")[0].trim().replace(/"/g, "") || raw;
  return raw.split("@")[0] || raw;
}

function priorityReason(t: ThreadSummary): string {
  if (t.flags?.length) return t.flags.map((f) => f.replace(/_/g, " ")).join(", ");
  if ((t.priority_score ?? 0) >= 85) return "High urgency signals detected";
  if ((t.priority_score ?? 0) >= 60) return "Likely time-sensitive";
  return "Routine conversation";
}

function matchQueue(t: ThreadSummary, q: Queue) {
  if (q === "home" || q === "all") return true;
  if (q === "urgent") return (t.priority_score ?? 0) >= 80 || t.flags?.some((f) => /complaint|urgent|deadline|closing/.test(f));
  if (q === "needs_reply") return t.reply_status === "needs_reply" || t.reply_status === "draft_ready";
  if (q === "hot_leads") return (t.category === "lead" || t.flags?.includes("hot_lead")) && (t.priority_score ?? 0) >= 60;
  if (q === "waiting") return t.reply_status === "replied";
  return true;
}

function DraftPanel({ thread, detail }: { thread: ThreadSummary; detail: ThreadDetail | null }) {
  const name = sender(thread.last_from);
  const base = detail?.summary || thread.summary || thread.subject || "your message";
  const suggested = `Hi ${name},\n\nThanks for reaching out. I reviewed your message about ${base}. I'd be happy to help and can follow up with the details you need.\n\nLet me know your preferred timing and I'll get back to you promptly.\n\nBest,\n[Your name]`;
  const [text, setText] = useState(suggested);
  useEffect(() => { setText(suggested); }, [suggested]);
  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div className="label">AI draft reply</div>
      <textarea className="textarea" style={{ minHeight: 140 }} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="draft-actions">
        <button className="btn primary"><Send size={14} /> Send reply</button>
        <button className="btn">Save draft</button>
        <button className="btn ghost">Regenerate</button>
      </div>
      <div className="sub" style={{ marginTop: 6 }}>Always review before sending. Nothing is sent automatically.</div>
    </div>
  );
}

function DetailPane({ thread, onRefresh }: { thread: ThreadSummary | null; onRefresh: () => void }) {
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!thread) { setDetail(null); return; }
    let c = false; setLoading(true);
    get<ThreadDetail>(`/emails/threads/${thread.id}`)
      .then((d) => { if (!c) setDetail(d); }).catch(() => { if (!c) setDetail(null); })
      .finally(() => { if (!c) setLoading(false); });
    return () => { c = true; };
  }, [thread?.id]);
  if (!thread) return <div className="panel"><div className="empty"><h2>Select a conversation</h2><p>Choose a thread to see the AI brief, messages, and draft reply.</p></div></div>;
  return (
    <div className="stack">
      <div className="panel ai-brief">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ minWidth: 0 }}>
            <div className="label">AI brief</div>
            <h3 style={{ margin: 0 }}>{thread.subject || "(no subject)"}</h3>
            <div className="sub">From {sender(thread.last_from)} · {formatTime(thread.last_activity_at)}</div>
          </div>
          <Link href={`/thread/${thread.id}`} className="btn sm ghost">Open <ArrowRight size={14} /></Link>
        </div>
        <div className="row" style={{ flexWrap: "wrap", marginTop: 8 }}>
          <ScorePill score={thread.priority_score} />
          <CategoryChip category={thread.category} />
          <ReplyStatusChip status={thread.reply_status} />
          {(thread.flags || []).slice(0, 3).map((f) => <FlagChip key={f} flag={f} />)}
        </div>
        <p style={{ margin: "10px 0 0", fontSize: 13.5, color: "var(--ink-soft)" }}>{detail?.summary || thread.summary || "AI summary will appear after processing."}</p>
        <div className="brief-reason"><strong>Why prioritized:</strong> {priorityReason(thread)}</div>
      </div>

      <div className="panel">
        <h3>Suggested next step</h3>
        <div className="sub">
          {thread.reply_status === "needs_reply" || thread.reply_status === "draft_ready"
            ? "Reply promptly with a clear answer and proposed next step. Review the draft below."
            : thread.reply_status === "replied"
            ? "Waiting on their response. Set a follow-up if you need one."
            : "Review this thread and decide if a response or task is needed."}
        </div>
        <DraftPanel thread={thread} detail={detail} />
      </div>

      <div className="panel">
        <h3>Conversation</h3>
        {loading && <div className="sub">Loading messages…</div>}
        {!loading && detail?.emails?.length ? (
          <div className="stack" style={{ gap: 10 }}>
            {detail.emails.slice(-3).map((e) => (
              <div key={e.id} style={{ padding: 10, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-muted)" }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong style={{ fontSize: 13 }}>{sender(e.from_addr)}</strong>
                  <span className="sub">{formatTime(e.received_at)}</span>
                </div>
                <div className="sub" style={{ marginTop: 4, display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                  {e.ai_summary || e.body?.slice(0, 280) || "(no content)"}
                </div>
              </div>
            ))}
            {detail.emails.length > 3 && <Link href={`/thread/${thread.id}`} className="back-link">View full thread ({detail.emails.length} messages)</Link>}
          </div>
        ) : !loading ? <div className="sub">No messages loaded yet. Sync and process to see details.</div> : null}
      </div>
    </div>
  );
}

export default function InboxPage() {
  const { activeId, processAll, dataVersion, busy } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<Queue>("home");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!activeId) return;
    try {
      const [tr, st] = await Promise.all([
        get<{ threads: ThreadSummary[] }>(`/emails/inbox/${activeId}?limit=100&sort=priority&order=desc`),
        get<InboxStats>(`/emails/stats/${activeId}`).catch(() => null),
      ]);
      setThreads(tr.threads || []); setStats(st); setError(null);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoaded(true); }
  }, [activeId]);

  useEffect(() => { void load(); }, [load, dataVersion]);

  const counts = useMemo(() => {
    const c: Record<Queue, number> = { home: threads.length, urgent: 0, needs_reply: 0, hot_leads: 0, waiting: 0, all: threads.length };
    threads.forEach((t) => {
      if (matchQueue(t, "urgent")) c.urgent++;
      if (matchQueue(t, "needs_reply")) c.needs_reply++;
      if (matchQueue(t, "hot_leads")) c.hot_leads++;
      if (matchQueue(t, "waiting")) c.waiting++;
    });
    return c;
  }, [threads]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return threads.filter((t) => {
      if (!matchQueue(t, queue)) return false;
      if (!q) return true;
      const hay = `${t.subject} ${t.summary || ""} ${t.last_from || ""} ${t.category || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [threads, queue, search]);

  const homeGroups = useMemo(() => {
    if (queue !== "home") return null;
    const hot = threads.filter((t) => matchQueue(t, "hot_leads")).slice(0, 5);
    const urgent = threads.filter((t) => matchQueue(t, "urgent") && !hot.includes(t)).slice(0, 5);
    const needReply = threads.filter((t) => matchQueue(t, "needs_reply") && !hot.includes(t) && !urgent.includes(t)).slice(0, 6);
    return { hot, urgent, needReply };
  }, [threads, queue]);

  const selected = useMemo(() => {
    if (selectedId && filtered.some((t) => t.id === selectedId)) return filtered.find((t) => t.id === selectedId)!;
    return filtered[0] || null;
  }, [filtered, selectedId]);

  async function onProcess() {
    try { const r = await processAll(); setNotice(`Processed ${r.processed} emails`); await load(); }
    catch { setNotice("Processing failed"); }
    setTimeout(() => setNotice(null), 2500);
  }

  if (!activeId) return <div className="empty"><h2>Connect Gmail to get started</h2><p>Once connected, your inbox will be prioritized and summarized here.</p></div>;

  const list = queue === "home" ? (homeGroups ? [...homeGroups.urgent, ...homeGroups.hot, ...homeGroups.needReply].filter((v,i,a)=>a.findIndex(x=>x.id===v.id)===i) : []) : filtered;

  return (
    <div className="stack">
      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="notice-banner">{notice}</div>}

      <div className="workspace">
        <aside className="queue-rail">
          <div className="card card-pad">
            <div className="label">Queues</div>
            <div className="queue-list">
              {QUEUES.map((q) => (
                <button key={q.id} className={`queue-btn ${queue === q.id ? "active" : ""}`} onClick={() => setQueue(q.id)}>
                  <span>{q.label}</span><span className="queue-count">{counts[q.id]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="card card-pad stack" style={{ gap: 8 }}>
            <div className="label">Quick actions</div>
            <button className="btn sm" onClick={() => void onProcess()} disabled={busy}><Sparkles size={14} /> Run AI on inbox</button>
            <Link href="/digest" className="btn sm ghost">View daily digest</Link>
            <Link href="/actions" className="btn sm ghost">Open action items</Link>
          </div>
        </aside>

        <section className="list-pane">
          <div className="kpi-strip">
            <div className="kpi"><div className="kpi-label">Unread</div><div className="kpi-value">{stats?.unread ?? threads.reduce((a,t)=>a+(t.unread||0),0)}</div><div className="kpi-meta">Needs your attention</div></div>
            <div className="kpi"><div className="kpi-label">Needs reply</div><div className="kpi-value">{counts.needs_reply}</div><div className="kpi-meta">Draft or respond</div></div>
            <div className="kpi"><div className="kpi-label">Hot leads</div><div className="kpi-value">{counts.hot_leads}</div><div className="kpi-meta">High-intent threads</div></div>
            <div className="kpi"><div className="kpi-label">Urgent</div><div className="kpi-value">{counts.urgent}</div><div className="kpi-meta">Deadlines & risks</div></div>
          </div>

          <div className="pill-row" style={{ marginTop: 2 }}>
            {QUEUES.map((q) => (
              <button key={q.id} className={`pill ${queue === q.id ? "active" : ""}`} onClick={() => setQueue(q.id)}>
                {q.label} · {counts[q.id]}
              </button>
            ))}
          </div>

          <div className="toolbar">
            <div className="search"><Search size={15} color="var(--muted)" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search sender, subject, summary…" /></div>
            <button className="btn sm" onClick={() => void onProcess()} disabled={busy}><Sparkles size={14} /> Process</button>
          </div>

          {queue === "home" && homeGroups && (
            <div className="grid-3">
              <div className="card card-pad"><div className="row" style={{ justifyContent: "space-between" }}><div className="label" style={{ margin: 0 }}>Hot leads</div><Zap size={14} color="var(--hot)" /></div><div className="kpi-value">{homeGroups.hot.length}</div><button className="btn sm ghost" onClick={() => setQueue("hot_leads")}>Review <ChevronRight size={14} /></button></div>
              <div className="card card-pad"><div className="row" style={{ justifyContent: "space-between" }}><div className="label" style={{ margin: 0 }}>Needs reply now</div><Clock size={14} color="var(--warn)" /></div><div className="kpi-value">{homeGroups.urgent.length + homeGroups.needReply.length}</div><button className="btn sm ghost" onClick={() => setQueue("needs_reply")}>Open queue <ChevronRight size={14} /></button></div>
              <div className="card card-pad"><div className="row" style={{ justifyContent: "space-between" }}><div className="label" style={{ margin: 0 }}>Daily brief</div><Sparkles size={14} color="var(--primary)" /></div><div className="sub">Hot leads, deadlines & follow-ups in one page.</div><Link href="/digest" className="btn sm ghost">View digest <ChevronRight size={14} /></Link></div>
            </div>
          )}

          <div className="thread-list">
            {!loaded && <div className="card card-pad sub">Loading inbox…</div>}
            {loaded && list.length === 0 && (
              <div className="empty"><h2>No conversations in this view</h2><p>Try a different queue, sync your inbox, or run AI processing.</p></div>
            )}
            {list.map((t) => (
              <article key={t.id} className={`thread-row ${selected?.id === t.id ? "selected" : ""} ${t.unread ? "unread" : ""}`} onClick={() => setSelectedId(t.id)}>
                <span className={`dot ${t.unread ? "" : "muted-dot"}`} aria-hidden />
                <div className="thread-main">
                  <div className="thread-top">
                    <span className="thread-from">{sender(t.last_from)}</span>
                    <span className="thread-time">{formatTime(t.last_activity_at)}</span>
                  </div>
                  <div className="thread-subject">{t.subject || "(no subject)"}</div>
                  <div className="thread-summary">{t.summary || "AI summary pending — run processing to analyze this thread."}</div>
                  <div className="thread-meta">
                    <ScorePill score={t.priority_score} />
                    <CategoryChip category={t.category} />
                    <ReplyStatusChip status={t.reply_status} />
                    {(t.flags || []).slice(0, 2).map((f) => <FlagChip key={f} flag={f} />)}
                  </div>
                  <div className="thread-actions" onClick={(e) => e.stopPropagation()}>
                    <Link href={`/thread/${t.id}`} className="btn sm primary">Open</Link>
                    <button className="btn sm" onClick={() => void patch(`/emails/threads/${t.id}`, { is_read: true }).then(load)}>Mark read</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="detail-pane desktop-only">
          <DetailPane thread={selected} onRefresh={load} />
        </aside>
      </div>
    </div>
  );
}
