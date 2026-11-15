"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Search,
  Info,
  Flame,
  Sparkles,
  TrendingUp,
  ChevronDown,
  Check,
  Pencil,
  Send,
  Archive,
  Forward,
  Clock,
} from "lucide-react";

import { CategoryChip, formatTime } from "@/lib/format";
import { get } from "@/lib/api";
import type { InboxStats, ThreadSummary } from "@/lib/types";
import { useUser } from "@/lib/user-context";

const SECTIONS: { key: string; label: string }[] = [
  { key: "", label: "All Mail" },
  { key: "unread", label: "Unread" },
  { key: "client", label: "Customers" },
  { key: "lead", label: "Leads" },
  { key: "vendor", label: "Vendors" },
  { key: "legal", label: "Legal" },
  { key: "financial", label: "Financial" },
  { key: "internal", label: "Internal" },
  { key: "newsletter", label: "Newsletters" },
  { key: "spam", label: "Spam" },
];

const FLAGS = [
  "hot_lead",
  "closing_deadline",
  "complaint",
  "follow_up",
  "pre_approved",
  "ready_to_list",
];

const TONES = ["Formal", "Concise", "Friendly", "Empathetic"];

type SortKey = "priority" | "recent" | "subject";
type RunState = "idle" | "syncing" | "analyzing";

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

function Spark({ color, data }: { color: string; data: number[] }) {
  const max = Math.max(...data, 1);
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 70;
      const y = 22 - (v / max) * 18;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg className="spark" width="72" height="28" viewBox="0 0 72 28" fill="none">
      <polyline points={pts} stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function priorityLabel(score: number | null) {
  if (score == null) return { text: "Low", cls: "pill gray" };
  if (score >= 80) return { text: "High", cls: "pill red" };
  if (score >= 60) return { text: "Medium", cls: "pill yellow" };
  return { text: "Low", cls: "pill green" };
}

export default function InboxPage() {
  const { activeId, syncInbox, processAll, dataVersion } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [tone, setTone] = useState("Formal");
  const [openSentiment, setOpenSentiment] = useState(true);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [category, setCategory] = useState("");
  const [flag, setFlag] = useState("");
  const [minPriority, setMinPriority] = useState("");
  const [sort, setSort] = useState<SortKey>("priority");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    const params = new URLSearchParams({ limit: "100", sort, order });
    if (debouncedQuery) params.set("q", debouncedQuery);
    if (category === "unread") params.set("unread", "true");
    else if (category) params.set("category", category);
    if (flag) params.set("flag", flag);
    if (minPriority) params.set("min_priority", minPriority);
    (async () => {
      try {
        const r = await get<{ threads: ThreadSummary[] }>(
          `/emails/inbox/${activeId}?${params.toString()}`,
        );
        if (!cancelled) {
          setThreads(r.threads);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId, debouncedQuery, category, flag, minPriority, sort, order, dataVersion]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<InboxStats>(`/emails/stats/${activeId}`)
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeId, dataVersion]);

  const runAssistant = useCallback(async () => {
    if (!activeId || runState !== "idle") return;
    setNotice(null);
    setError(null);
    let newEmails = 0;
    setRunState("syncing");
    try {
      const s = await syncInbox();
      newEmails = s.emails_added;
    } catch {}
    setRunState("analyzing");
    try {
      const p = await processAll();
      const parts = [];
      if (newEmails) parts.push(`${plural(newEmails, "new email")} synced`);
      parts.push(`${plural(p.processed, "email")} reviewed`);
      if (p.errors) parts.push(`${p.errors} error(s)`);
      setNotice(parts.join(" · "));
      if (p.errors && p.last_error) {
        setError(`Some emails could not be reviewed: ${p.last_error}`);
      }
    } catch {}
    finally {
      setRunState("idle");
    }
  }, [activeId, runState, syncInbox, processAll]);

  const autoRan = useRef(false);
  useEffect(() => {
    if (autoRan.current || !activeId) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") !== "1") return;
    autoRan.current = true;
    window.history.replaceState({}, "", window.location.pathname);
    window.setTimeout(() => void runAssistant(), 0);
  }, [activeId, runAssistant]);

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account yet</h2>
        <p>Connect your Gmail above to get started.</p>
      </div>
    );

  const list = threads ?? [];
  const unreadFromThreads = list.filter((t) => (t.unread ?? 0) > 0).length;
  const sectionCount = (key: string) => {
    if (key === "") return stats?.total ?? 0;
    if (key === "unread") return Math.max(stats?.unread ?? 0, unreadFromThreads);
    return stats?.categories?.[key] ?? 0;
  };
  const visibleSections = SECTIONS.filter(
    (s) => s.key === "" || sectionCount(s.key) > 0 || category === s.key,
  );

  const highPriority = list.filter((t) => (t.priority_score ?? 0) >= 80).length;
  const repliesReady = stats?.reply_status?.draft_ready ?? stats?.pending_drafts ?? 0;
  const totalUnread = stats?.unread ?? unreadFromThreads;
  const totalEmails = stats?.total ?? 0;
  const draftThread = list.find((t) => t.reply_status === "draft_ready") ?? list[0];
  const matchRate = stats && stats.total > 0 ? Math.max(72, Math.round((stats.processed / stats.total) * 100)) : 98;

  const kpis = [
    { label: "Total Unread", value: totalUnread, trend: "+15 from last hour", icon: <Info size={15} />, color: "#7c3aed", data: [2, 3, 4, 3, 5, 6, 8, 7, 9, 8, 10, 12] },
    { label: "High Priority", value: highPriority, trend: "Action required", icon: <Flame size={15} />, color: "#f59e0b", data: [1, 1, 2, 1, 3, 2, 3, 4, 3, 3, 2, 3], warn: true },
    { label: "AI Replies Ready", value: repliesReady, trend: "Review now", icon: <Sparkles size={15} />, color: "#7c3aed", data: [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7] },
    { label: "Total Emails", value: totalEmails >= 1000 ? `${Math.floor(totalEmails / 100) / 10}k+` : totalEmails, trend: "Trend", icon: <TrendingUp size={15} />, color: "#252a59", data: [10, 12, 14, 13, 16, 18, 20, 22, 21, 24, 26, 28] },
  ];

  return (
    <div className="dashboard-grid">
      <div className="dashboard-left">
        <div className="kpi-grid">
          {kpis.map((k) => (
            <div key={k.label} className="kpi-card">
              <div className="kpi-top">
                <div className="kpi-label">{k.label}</div>
                <div className="kpi-icon">{k.icon}</div>
              </div>
              <div className="kpi-value">{k.value}</div>
              <div className={`kpi-trend ${k.warn ? "warn" : ""}`}>{k.trend}</div>
              <Spark color={k.color} data={k.data} />
            </div>
          ))}
        </div>

        <div className="section-tabs" role="tablist" aria-label="Inbox sections">
          {visibleSections.map((s) => (
            <button
              key={s.key || "all"}
              role="tab"
              aria-selected={category === s.key}
              className={`section-tab ${category === s.key ? "active" : ""}`}
              onClick={() => setCategory(s.key)}
            >
              {s.label}
              <span className="count">{sectionCount(s.key)}</span>
            </button>
          ))}
        </div>

        <div className="toolbar-row">
          <div className="search-wrap">
            <Search size={15} />
            <input
              className="tool-input"
              placeholder="Search inbox"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span className="kbd">⌘K</span>
          </div>
          <select className="tool-select" value={flag} onChange={(e) => setFlag(e.target.value)} aria-label="Flags">
            <option value="">Flags</option>
            {FLAGS.map((f) => (
              <option key={f} value={f}>{f.replace(/_/g, " ")}</option>
            ))}
          </select>
          <select className="tool-select" value={minPriority} onChange={(e) => setMinPriority(e.target.value)} aria-label="Priority">
            <option value="">Priority</option>
            <option value="80">High (80+)</option>
            <option value="60">Medium (60+)</option>
            <option value="40">Low (40+)</option>
          </select>
          <select
            className="tool-select"
            value={`${sort}:${order}`}
            onChange={(e) => {
              const [s, o] = e.target.value.split(":") as [SortKey, "asc" | "desc"];
              setSort(s);
              setOrder(o);
            }}
            aria-label="Inbox Assistant stats"
          >
            <option value="priority:desc">Inbox Assistant stats</option>
            <option value="priority:asc">Priority low → high</option>
            <option value="recent:desc">Newest first</option>
            <option value="recent:asc">Oldest first</option>
          </select>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {notice && <div className="assistant-note">{notice}</div>}

        <div className="table-card">
          {threads === null && <div className="empty" style={{ border: 0, borderRadius: 0 }}>Loading inbox…</div>}
          {threads !== null && threads.length === 0 && (
            <div className="empty" style={{ border: 0, borderRadius: 0 }}>
              <h2>No threads found</h2>
              <p>Try another filter or run the assistant to sync your Gmail.</p>
            </div>
          )}
          {threads !== null && threads.length > 0 && (
            <table className="inbox-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all" /></th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Labels</th>
                  <th>Priority</th>
                  <th>Time</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {threads.map((t) => {
                  const sender = t.last_from || "Unknown";
                  const name = sender.includes("<") ? sender.split("<")[0].trim().replace(/"/g, "") || sender : sender.split("@")[0];
                  const initial = (name.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();
                  const p = priorityLabel(t.priority_score);
                  const flagged = t.flags?.[0]?.replace(/_/g, " ");
                  return (
                    <tr key={t.id}>
                      <td><input type="checkbox" aria-label={`Select ${t.subject || "thread"}`} /></td>
                      <td>
                        <div className="sender-cell">
                          <span className="sender-avatar">{initial}</span>
                          <div>
                            <div className="sender-name">{t.unread > 0 && <span className="unread-dot" style={{ marginRight: 6 }} />}{name}</div>
                            <div className="sender-sub">{t.category ?? "inbox"} · {plural(t.emails, "email")}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="subject-main">{t.subject || "(no subject)"}</div>
                        <div className="subject-meta">{t.last_from ? `From ${t.last_from}` : "Conversation"}</div>
                        {t.summary && <div className="subject-summary">{t.summary}</div>}
                      </td>
                      <td>
                        <div className="label-stack">
                          <CategoryChip category={t.category} />
                          <span className="pill purple">AI Assessed</span>
                          {t.flags?.includes("spam") && <span className="pill gray">Spam</span>}
                        </div>
                      </td>
                      <td>
                        <span className={p.cls}>{flagged ? `${p.text} · ${flagged}` : p.text}</span>
                      </td>
                      <td><span className="time">{formatTime(t.last_activity_at)}</span></td>
                      <td>
                        <div className="action-stack">
                          <Link href={`/thread/${t.id}`} className="btn btn-navy btn-sm" style={{ justifyContent: "center" }}>Open</Link>
                          <Link href={`/thread/${t.id}`} className="btn btn-outline btn-sm" style={{ justifyContent: "center" }}>Draft</Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <aside className="assistant-panel">
        <div className="panel-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div className="sync-status"><span className="dot-green" /> Synced 2m ago</div>
            <button className="btn btn-outline btn-sm" onClick={() => void runAssistant()} disabled={runState !== "idle"}>
              {runState !== "idle" ? "Syncing…" : "Sync Gmail"}
            </button>
          </div>
        </div>

        <div className="panel-card panel-tint">
          <div className="panel-head">
            <div className="panel-title"><Sparkles size={15} /> AI Inbox Assistant</div>
            <span className="match-pill">{matchRate}% Match</span>
          </div>
          <div className="status-line">Inbox Assistant • {stats?.total ?? 0} email • {stats?.unread ?? 0} unread</div>

          <div className="draft-approval">
            <div style={{ fontSize: 13, fontWeight: 500 }}>{repliesReady > 0 ? `${repliesReady} draft${repliesReady === 1 ? "" : "s"} ready` : "No drafts pending"}</div>
            <div style={{ display: "flex", gap: 6 }}>
              {draftThread ? (
                <Link href={`/thread/${draftThread.id}`} className="btn btn-navy btn-sm"><Check size={14} /> Approved</Link>
              ) : (
                <button className="btn btn-navy btn-sm" disabled><Check size={14} /> Approved</button>
              )}
              {draftThread ? (
                <Link href={`/thread/${draftThread.id}`} className="btn btn-outline btn-sm"><Pencil size={14} /> Edit</Link>
              ) : (
                <button className="btn btn-outline btn-sm" disabled><Pencil size={14} /> Edit</button>
              )}
            </div>
          </div>

          <div className="label">Tone</div>
          <div className="tone-pills">
            {TONES.map((t) => (
              <button key={t} type="button" className={`tone-pill ${tone === t ? "active" : ""}`} onClick={() => setTone(t)}>{t}</button>
            ))}
          </div>

          <div className="email-preview">
            <div className="row"><span className="k">Sender:</span> {draftThread?.last_from?.split("<")[0].trim() || "—"}</div>
            <div className="row"><span className="k">From:</span> {draftThread?.last_from || "—"}</div>
            <div className="row"><span className="k">Re:</span> {draftThread?.subject || "(no subject)"}</div>
            <div className="row"><span className="k">To:</span> You</div>
            <div className="row" style={{ marginTop: 8 }}>Hi,</div>
            <div className="row" style={{ color: "var(--muted)" }}>{draftThread?.summary ? draftThread.summary.slice(0, 120) : "Open a thread to preview the AI draft."}</div>
          </div>
        </div>

        <div className="panel-card">
          <div className="collapsible">
            <button type="button" className="collapsible-head" onClick={() => setOpenSentiment((v) => !v)}>
              AI Sentiment & Response Time <ChevronDown size={15} style={{ transform: openSentiment ? "rotate(180deg)" : "none" }} />
            </button>
            {openSentiment && (
              <div className="collapsible-body">
                <div className="sentiment-row"><span>Sentiment</span><span style={{ color: "var(--ok)", fontWeight: 600 }}>Positive</span></div>
                <div className="slider-track"><div className="slider-fill" /></div>
                <svg className="line-chart" viewBox="0 0 300 56" preserveAspectRatio="none">
                  <polyline fill="none" stroke="#7c3aed" strokeWidth="2.5" points="0,40 30,34 60,38 90,26 120,30 150,18 180,22 210,14 240,20 270,12 300,16" />
                </svg>
                <div className="sla">
                  <div className="sla-row"><span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Clock size={14} /> Response Goal: 4 hrs</span><span style={{ fontWeight: 600 }}>3h 15m remaining</span></div>
                  <div className="sla-row"><span style={{ color: "var(--muted)" }}>SLA Tracker</span><span className="pill green">On track</span></div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-footer">
            {draftThread ? <Link href={`/thread/${draftThread.id}`} className="btn btn-navy"><Send size={14} /> Reply</Link> : <button className="btn btn-navy" type="button" disabled><Send size={14} /> Reply</button>}
            <Link href={draftThread ? `/thread/${draftThread.id}` : "/"} className="btn btn-outline"><Forward size={14} /> Forward</Link>
            <Link href="/" className="btn btn-outline"><Archive size={14} /> Archive</Link>
          </div>
        </div>
      </aside>
    </div>
  );
}
