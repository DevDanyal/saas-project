"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  Info,
  Flame,
  Sparkles,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Check,
  Pencil,
  Send,
  Archive,
  Forward,
  Clock,
  Reply,
  X,
} from "lucide-react";
import { CategoryChip } from "@/lib/format";
import { get, patch } from "@/lib/api";
import type { InboxStats, ThreadDetail, ThreadSummary } from "@/lib/types";
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

const TONES = ["Formal", "Concise", "Friendly", "Empathetic"] as const;
type Tone = (typeof TONES)[number];

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
  if (score == null) return { text: "Low", cls: "pill green", key: "Low" as const };
  if (score >= 80) return { text: "High", cls: "pill red", key: "High" as const };
  if (score >= 60) return { text: "Medium", cls: "pill yellow", key: "Medium" as const };
  return { text: "Low", cls: "pill green", key: "Low" as const };
}

function formatCellTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: true });
}

function senderName(from: string | null | undefined) {
  const sender = from || "Unknown";
  const name = sender.includes("<") ? sender.split("<")[0].trim().replace(/"/g, "") || sender : sender.split("@")[0] || sender;
  const initial = (name.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();
  return { sender, name, initial };
}

function rewriteTone(base: string, tone: Tone) {
  const text = base.trim();
  if (!text) return "";
  const body = text.replace(/^(hi|hello|dear)[^,\n]*[,\n]*/i, "").trim();
  const first = body || text;
  switch (tone) {
    case "Concise":
      return `Hi,\n\n${first.split(/\n+/).slice(0, 2).join(" ")}\n\nBest,\n[Your Name]`;
    case "Friendly":
      return `Hi there,\n\nHope you're doing well! ${first}\n\nWarmly,\n[Your Name]`;
    case "Empathetic":
      return `Hi,\n\nThank you for reaching out. I understand your concern, and I appreciate your patience. ${first}\n\nBest regards,\n[Your Name]`;
    default:
      return `Dear Recipient,\n\n${first}\n\nSincerely,\n[Your Name]`;
  }
}

export default function InboxPage() {
  const { activeId, syncInbox, dataVersion, refreshData } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tone, setTone] = useState<Tone>("Formal");
  const [openDrafts, setOpenDrafts] = useState(false);
  const [busyThread, setBusyThread] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState<string>("2m ago");

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [flag, setFlag] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [statsFilter, setStatsFilter] = useState("");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [priorityMenu, setPriorityMenu] = useState<string | null>(null);
  const [draftBase, setDraftBase] = useState("");
  const [draftText, setDraftText] = useState("");
  const [draftEditing, setDraftEditing] = useState(false);
  const [draftApproved, setDraftApproved] = useState(false);
  const computedDraft = useMemo(() => (draftBase ? rewriteTone(draftBase, tone) : ""), [draftBase, tone]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<{ threads: ThreadSummary[] }>(`/emails/inbox/${activeId}?limit=100&sort=priority&order=desc`)
      .then((r) => {
        if (!cancelled) {
          setThreads(r.threads);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => { cancelled = true; };
  }, [activeId, dataVersion]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<InboxStats>(`/emails/stats/${activeId}`)
      .then((s) => { if (!cancelled) setStats(s); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeId, dataVersion]);

  const list = useMemo(() => {
    const base = threads ?? [];
    const q = query.trim().toLowerCase();
    return base.filter((t) => {
      if (category === "unread" && !(t.unread > 0)) return false;
      if (category && category !== "unread" && (t.category || "") !== category) return false;
      if (flag && !(t.flags || []).includes(flag)) return false;
      if (priorityFilter === "high" && !((t.priority_score ?? 0) >= 80)) return false;
      if (priorityFilter === "medium" && !((t.priority_score ?? 0) >= 60 && (t.priority_score ?? 0) < 80)) return false;
      if (priorityFilter === "low" && !((t.priority_score ?? 0) < 60)) return false;
      if (statsFilter === "high" && !((t.priority_score ?? 0) >= 80)) return false;
      if (statsFilter === "unread" && !(t.unread > 0)) return false;
      if (statsFilter === "drafts" && t.reply_status !== "draft_ready") return false;
      if (q) {
        const hay = `${t.subject || ""} ${t.last_from || ""} ${t.summary || ""} ${t.category || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [threads, category, flag, priorityFilter, statsFilter, query]);

  const effectiveSelectedId = selectedId && list.some((t) => t.id === selectedId) ? selectedId : (list[0]?.id ?? null);

  useEffect(() => {
    if (!effectiveSelectedId) return;
    let cancelled = false;
    get<ThreadDetail>(`/emails/threads/${effectiveSelectedId}`)
      .then((d) => {
        if (cancelled) return;
        const base = d.summary || d.emails?.[d.emails.length - 1]?.ai_summary || `Thank you for your message regarding "${d.subject || "your email"}". I will review the details and get back to you shortly.`;
        setDraftBase(base);
        setDraftApproved(false);
        setDraftEditing(false);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [effectiveSelectedId]);

  const sectionCount = useCallback((key: string) => {
    const base = threads ?? [];
    if (key === "") return base.length;
    if (key === "unread") return base.filter((t) => t.unread > 0).length;
    return base.filter((t) => t.category === key).length;
  }, [threads]);

  const visibleSections = SECTIONS.filter((s) => s.key === "" || sectionCount(s.key) > 0 || category === s.key);

  const allChecked = list.length > 0 && list.every((t) => checked.has(t.id));
  const toggleAll = () => {
    setChecked(() => {
      if (allChecked) return new Set<string>();
      return new Set(list.map((t) => t.id));
    });
  };
  const toggleOne = (id: string) => {
    setChecked((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const updateThreadLocal = useCallback((id: string, patcher: (t: ThreadSummary) => ThreadSummary) => {
    setThreads((prev) => prev ? prev.map((t) => (t.id === id ? patcher(t) : t)) : prev);
  }, []);

  const markSpam = useCallback(async (id: string) => {
    setBusyThread(id);
    setError(null);
    try {
      await patch(`/emails/threads/${id}`, { category: "spam" });
      updateThreadLocal(id, (t) => ({ ...t, category: "spam" }));
      refreshData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyThread(null);
    }
  }, [refreshData, updateThreadLocal]);

  const applyPriority = useCallback(async (id: string, score: number) => {
    setPriorityMenu(null);
    setBusyThread(id);
    setError(null);
    try {
      await patch(`/emails/threads/${id}`, { priority_score: score });
      updateThreadLocal(id, (t) => ({ ...t, priority_score: score }));
      refreshData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyThread(null);
    }
  }, [refreshData, updateThreadLocal]);

  const onReply = useCallback((id: string) => {
    setSelectedId(id);
    setDraftEditing(false);
    window.setTimeout(() => {
      document.getElementById("assistant-reply")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 50);
  }, []);

  const doSync = useCallback(async () => {
    if (!activeId || syncing) return;
    setSyncing(true);
    setNotice(null);
    setError(null);
    try {
      const s = await syncInbox();
      setLastSynced("just now");
      setNotice(s.emails_added ? `${plural(s.emails_added, "new email")} synced` : "Inbox synced");
      refreshData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncing(false);
    }
  }, [activeId, syncing, syncInbox, refreshData]);

  const autoRan = useRef(false);
  useEffect(() => {
    if (autoRan.current || !activeId) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") !== "1") return;
    autoRan.current = true;
    window.history.replaceState({}, "", window.location.pathname);
    window.setTimeout(() => void doSync(), 0);
  }, [activeId, doSync]);

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account yet</h2>
        <p>Connect your Gmail above to get started.</p>
      </div>
    );

  const baseList = threads ?? [];
  const unreadFromThreads = baseList.filter((t) => (t.unread ?? 0) > 0).length;
  const highPriority = baseList.filter((t) => (t.priority_score ?? 0) >= 80).length;
  const repliesReady = stats?.reply_status?.draft_ready ?? stats?.pending_drafts ?? baseList.filter((t) => t.reply_status === "draft_ready").length;
  const totalUnread = stats?.unread ?? unreadFromThreads;
  const totalEmails = baseList.length || stats?.total || 0;
  const selected = effectiveSelectedId ? baseList.find((t) => t.id === effectiveSelectedId) ?? list[0] ?? null : list[0] ?? null;

  const kpis = [
    { label: "Total Unread", value: totalUnread, trend: "+15 from last hour", icon: <Info size={15} />, color: "#7c3aed", data: [2, 3, 4, 3, 5, 6, 8, 7, 9, 8, 10, 12] },
    { label: "High Priority", value: highPriority, trend: "Action required", icon: <Flame size={15} />, color: "#f59e0b", data: [1, 1, 2, 1, 3, 2, 3, 4, 3, 3, 2, 3], warn: true },
    { label: "AI Replies Ready", value: repliesReady, trend: "Review now", icon: <Sparkles size={15} />, color: "#7c3aed", data: [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7] },
    { label: "Total Emails", value: totalEmails >= 1000 ? `${Math.floor(totalEmails / 100) / 10}k+` : totalEmails, trend: "Trend", icon: <TrendingUp size={15} />, color: "#252a59", data: [10, 12, 14, 13, 16, 18, 20, 22, 21, 24, 26, 28] },
  ];

  return (
    <div className="dashboard-grid flex w-full gap-6 items-start">
      <div className="dashboard-left flex-1 min-w-0">
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
            <input className="tool-input" placeholder="Search inbox" value={query} onChange={(e) => setQuery(e.target.value)} />
            <span className="kbd">⌘K</span>
          </div>
          <select className="tool-select" value={flag} onChange={(e) => setFlag(e.target.value)} aria-label="Flags">
            <option value="">Flags</option>
            <option value="hot_lead">hot lead</option>
            <option value="closing_deadline">closing deadline</option>
            <option value="complaint">complaint</option>
            <option value="follow_up">follow up</option>
            <option value="pre_approved">pre approved</option>
            <option value="ready_to_list">ready to list</option>
          </select>
          <select className="tool-select" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} aria-label="Priority">
            <option value="">Priority</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select className="tool-select" value={statsFilter} onChange={(e) => setStatsFilter(e.target.value)} aria-label="Inbox Assistant stats">
            <option value="">Inbox Assistant stats</option>
            <option value="high">High priority</option>
            <option value="unread">Unread</option>
            <option value="drafts">Drafts ready</option>
          </select>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {notice && <div className="assistant-note">{notice}</div>}

        <div className="table-card">
          {threads === null && <div className="empty" style={{ border: 0, borderRadius: 0 }}>Loading inbox…</div>}
          {threads !== null && list.length === 0 && (
            <div className="empty" style={{ border: 0, borderRadius: 0 }}>
              <h2>No threads found</h2>
              <p>Try another filter or run the assistant to sync your Gmail.</p>
            </div>
          )}
          {threads !== null && list.length > 0 && (
            <table className="inbox-table table-fixed w-full">
              <thead>
                <tr>
                  <th className="col-check w-10"><input type="checkbox" aria-label="Select all" checked={allChecked} onChange={toggleAll} /></th>
                  <th className="col-sender w-40">Sender</th>
                  <th className="col-subject w-auto">Subject</th>
                  <th className="col-labels w-28">Labels</th>
                  <th className="col-priority w-20">Priority</th>
                  <th className="col-time w-20">Time</th>
                  <th className="col-actions w-32">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.map((t) => {
                  const { name, initial } = senderName(t.last_from);
                  const p = priorityLabel(t.priority_score);
                  const selectedRow = effectiveSelectedId === t.id;
                  return (
                    <tr key={t.id} className={selectedRow ? "row-selected" : ""} onClick={() => setSelectedId(t.id)} style={{ cursor: "pointer" }}>
                      <td className="col-check w-10" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" aria-label={`Select ${t.subject || "thread"}`} checked={checked.has(t.id)} onChange={() => toggleOne(t.id)} />
                      </td>
                      <td className="col-sender w-40">
                        <div className="sender-cell">
                          <span className="sender-avatar">{initial}</span>
                          <div className="min-w-0 flex-1">
                            <div className="sender-name truncate" title={name}>{t.unread > 0 && <span className="unread-dot" style={{ marginRight: 6 }} />}{name}</div>
                            <div className="sender-sub truncate" title={t.category || "inbox"}>{t.category ?? "inbox"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="col-subject w-auto">
                        <div className="subject-wrap min-w-0">
                          <div className="subject-main truncate" title={t.subject || "(no subject)"}>{t.subject || "(no subject)"}</div>
                          <div className="subject-meta truncate">{t.last_from ? `From ${t.last_from}` : "Conversation"}</div>
                          {t.summary && <div className="subject-summary line-clamp-2">{t.summary}</div>}
                        </div>
                      </td>
                      <td className="col-labels w-28">
                        <div className="label-stack">
                          {t.category === "spam" ? <span className="pill gray">Spam</span> : <CategoryChip category={t.category} />}
                          <span className="pill purple">AI Assessed</span>
                        </div>
                      </td>
                      <td className="col-priority w-20"><span className={p.cls}>{p.text}</span></td>
                      <td className="col-time w-20"><div className="time-cell whitespace-normal">{formatCellTime(t.last_activity_at)}</div></td>
                      <td className="col-actions w-32" onClick={(e) => e.stopPropagation()}>
                        <div className="action-stack">
                          <button type="button" className="btn btn-navy btn-sm btn-block rounded-lg" onClick={() => onReply(t.id)}><Reply size={13} /> Reply</button>
                          <button type="button" className="btn btn-outline btn-sm btn-block rounded-lg border-[#E2E8F0]" disabled={busyThread === t.id} onClick={() => void markSpam(t.id)}>Mark as Spam</button>
                          <div className="priority-menu-wrap" style={{ position: "relative" }}>
                            <button type="button" className="btn btn-outline btn-sm btn-block rounded-lg border-[#E2E8F0]" disabled={busyThread === t.id} onClick={() => setPriorityMenu((v) => (v === t.id ? null : t.id))}>
                              Set Priority <ChevronDown size={13} />
                            </button>
                            {priorityMenu === t.id && (
                              <div className="priority-menu">
                                <button type="button" onClick={() => void applyPriority(t.id, 90)}>High</button>
                                <button type="button" onClick={() => void applyPriority(t.id, 70)}>Medium</button>
                                <button type="button" onClick={() => void applyPriority(t.id, 40)}>Low</button>
                              </div>
                            )}
                          </div>
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

      <aside className="assistant-panel w-[350px] shrink-0" id="assistant-panel">
        <div className="panel-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div className="sync-status"><span className="dot-green" /> Synced {syncing ? "now…" : lastSynced}</div>
            <button className="btn btn-outline btn-sm" onClick={() => void doSync()} disabled={syncing}>
              {syncing ? <><span className="spin-sm" /> Syncing…</> : "Sync Gmail"}
            </button>
          </div>
        </div>

        <div className="panel-card panel-tint" id="assistant-reply">
          <div className="panel-head">
            <div className="panel-title"><Sparkles size={15} /> AI Inbox Assistant</div>
            <span className="match-pill">100% Match</span>
          </div>
          <div className="status-line">Inbox Assistant • {totalEmails} email • {totalUnread} unread</div>

          <div className="draft-approval">
            <div style={{ fontSize: 13, fontWeight: 500 }}>{repliesReady > 0 ? `${repliesReady} draft${repliesReady === 1 ? "" : "s"} ready` : "1 draft ready"}</div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className={`btn btn-sm ${draftApproved ? "btn-navy" : "btn-outline"}`} type="button" onClick={() => setDraftApproved((v) => !v)}><Check size={14} /> {draftApproved ? "Approved" : "Approve"}</button>
              <button className="btn btn-outline btn-sm" type="button" onClick={() => { setDraftText(computedDraft); setDraftEditing(true); }}><Pencil size={14} /> Edit</button>
            </div>
          </div>

          <div className="label">Tone</div>
          <div className="tone-pills">
            {TONES.map((t) => (
              <button key={t} type="button" className={`tone-pill ${tone === t ? "active" : ""}`} onClick={() => setTone(t)}>{t}</button>
            ))}
          </div>

          <div className="email-preview p-4">
            <div className="row"><span className="k">Sender:</span> {senderName(selected?.last_from).name || "—"}</div>
            <div className="row"><span className="k">From:</span> {selected?.last_from || "—"}</div>
            <div className="row"><span className="k">Re:</span> {selected?.subject || "(no subject)"}</div>
            <div className="row"><span className="k">To:</span> You</div>
            <div className="row" style={{ marginTop: 10, fontWeight: 600 }}>Draft reply</div>
            {!draftEditing ? (
              <div className="row" style={{ color: "var(--muted)", marginTop: 4, whiteSpace: "pre-wrap" }}>{computedDraft || "Select a thread to generate a draft."}</div>
            ) : (
              <div style={{ marginTop: 6 }}>
                <textarea className="draft-edit-area" value={draftText} onChange={(e) => setDraftText(e.target.value)} rows={6} />
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <button type="button" className="btn btn-navy btn-sm" onClick={() => { setDraftBase(draftText); setDraftEditing(false); }}><Check size={13} /> Save</button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => { setDraftEditing(false); }}><X size={13} /> Cancel</button>
                </div>
              </div>
            )}
          </div>

          <div className="panel-card p-0 mt-3 overflow-hidden" style={{ padding: 0, marginTop: 12 }}>
            <button type="button" className="collapsible-head w-full" onClick={() => setOpenDrafts((v) => !v)}>
              <span>Drafts in progress</span>
              <ChevronRight size={15} style={{ transform: openDrafts ? "rotate(90deg)" : "none", transition: "transform 0.15s" }} />
            </button>
            {openDrafts && (
              <div className="collapsible-body" style={{ paddingTop: 0, paddingBottom: 12 }}>
                <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
                  {repliesReady > 0 ? `${repliesReady} draft${repliesReady === 1 ? "" : "s"} in progress` : "No drafts in progress"}
                </div>
                {selected && <Link href={`/thread/${selected.id}`} className="btn btn-outline btn-sm" style={{ marginTop: 8, width: "100%", justifyContent: "center" }}>Open draft</Link>}
              </div>
            )}
          </div>
        </div>

        <div className="panel-card">
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
        </div>

        <div className="panel-card">
          <div className="panel-footer">
            {selected ? <Link href={`/thread/${selected.id}`} className="btn btn-navy"><Send size={14} /> Reply</Link> : <button className="btn btn-navy" type="button" disabled><Send size={14} /> Reply</button>}
            <Link href={selected ? `/thread/${selected.id}` : "/"} className="btn btn-outline"><Forward size={14} /> Forward</Link>
            <Link href="/" className="btn btn-outline"><Archive size={14} /> Archive</Link>
          </div>
        </div>
      </aside>
    </div>
  );
}
