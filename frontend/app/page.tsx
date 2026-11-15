"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Paperclip, Link as LinkIcon, Send, X, Sparkles, ChevronDown, SlidersHorizontal,
} from "lucide-react";
import { get, patch } from "@/lib/api";
import type { InboxStats, ThreadDetail, ThreadSummary } from "@/lib/types";
import { useUser } from "@/lib/user-context";

type Tone = "Formal" | "Concise" | "Friendly" | "Empathetic";
type Priority = "High" | "Medium" | "Low";
type Tab = "Inbox" | "Action Items" | "Daily Digest" | "Alerts" | "Settings";
type Filter = "All Mail" | "Unread" | "LinkedIn" | "High Priority";
type MobileFilter = "All" | "Categories" | "Action Items" | "Friendly";

const TONES: Tone[] = ["Formal", "Concise", "Friendly", "Empathetic"];
const TABS: Tab[] = ["Inbox", "Action Items", "Daily Digest", "Alerts", "Settings"];

function sparkPoints(data: number[]) {
  const max = Math.max(...data, 1);
  return data.map((v, i) => `${(i / (data.length - 1)) * 100},${30 - (v / max) * 24}`).join(" ");
}
function Sparkline({ color, data }: { color: string; data: number[] }) {
  return (
    <svg viewBox="0 0 100 30" className="sparkline" preserveAspectRatio="none" aria-hidden>
      <polyline points={sparkPoints(data)} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function senderDisplay(from: string | null | undefined) {
  const raw = (from || "Unknown").trim();
  const name = raw.includes("<") ? raw.split("<")[0].trim().replace(/"/g, "") || raw : raw.split("@")[0] || raw;
  const lower = raw.toLowerCase();
  const platform = lower.includes("linkedin") || name.toLowerCase().includes("linkedin") ? "LinkedIn" : lower.includes("gmail") ? "Gmail" : lower.includes("outlook") ? "Outlook" : "";
  return { name, label: platform ? `${name} on ${platform}` : name, platform };
}

function timeLabel(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function priorityFromScore(score: number | null | undefined): Priority {
  if ((score ?? 0) >= 80) return "High";
  if ((score ?? 0) >= 60) return "Medium";
  return "Low";
}
function scoreForPriority(p: Priority) { return p === "High" ? 90 : p === "Medium" ? 70 : 35; }

function baseDraft(thread: ThreadSummary | null, detail: ThreadDetail | null) {
  if (!thread) return "Select an email to generate a reply draft.";
  const summary = detail?.summary || thread.summary || `regarding "${thread.subject || "your message"}"`;
  return `Thank you for reaching out. I reviewed your message ${summary ? `about ${summary}` : ""}. I’d be happy to help and can follow up with the details you need.\n\nPlease let me know your preferred timing, and I’ll get back to you promptly.`;
}
function rewriteDraft(base: string, tone: Tone, name: string) {
  const body = base.trim();
  const greet = `Dear ${name || "there"},`;
  if (tone === "Concise") return `${greet}\n\n${body.split(/\n+/).slice(0, 2).join(" ")}\n\nBest regards,\nDev Danyal`;
  if (tone === "Friendly") return `${greet}\n\nHope you’re doing well! ${body}\n\nWarmly,\nDev Danyal`;
  if (tone === "Empathetic") return `${greet}\n\nThank you so much for your message — I appreciate you reaching out. ${body}\n\nKind regards,\nDev Danyal`;
  return `${greet}\n\n${body}\n\nSincerely,\nDev Danyal`;
}

type AssistantPanelProps = {
  mobile?: boolean;
  selected: ThreadSummary | null;
  tone: Tone;
  onTone: (t: Tone) => void;
  shownDraft: string;
  onDraftChange: (v: string) => void;
  onSend: () => void;
  onClose: () => void;
};

function AssistantPanel({ mobile, selected, tone, onTone, shownDraft, onDraftChange, onSend, onClose }: AssistantPanelProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">AI Inbox Assistant</h2>
          <div className="mt-1 inline-flex items-center rounded-full bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-white">100% Match</div>
        </div>
        {mobile ? (
          <button onClick={onClose} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600"><X size={16} /></button>
        ) : null}
      </div>

      <div className="mt-4">
        <div className="mb-2 text-xs font-medium text-slate-500">Tone</div>
        <div className="flex flex-wrap gap-2">
          {TONES.map((t) => (
            <button key={t} onClick={() => onTone(t)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${tone === t ? "bg-indigo-600 text-white" : "border border-slate-200 bg-white text-slate-600 hover:border-indigo-200"}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex-1">
        <div className="mb-2 text-xs font-medium text-slate-500">Draft</div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-sm">
          <textarea
            value={shownDraft}
            onChange={(e) => onDraftChange(e.target.value)}
            className="min-h-[220px] w-full resize-none border-0 bg-transparent text-sm leading-6 text-slate-700 outline-none"
            placeholder="Select an email to generate a draft..."
          />
        </div>
        {selected && <div className="mt-2 text-[11px] text-slate-500">Replying to: {senderDisplay(selected.last_from).label}</div>}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-200/80 pt-3">
        <div className="flex items-center gap-2 text-slate-400">
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-slate-100" title="Attach"><Paperclip size={16} /></button>
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-slate-100" title="Insert link"><LinkIcon size={16} /></button>
        </div>
        <button onClick={onSend} disabled={!selected} className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-sm hover:bg-emerald-600 disabled:opacity-50" aria-label="Send reply">
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-10 text-center shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 text-sm text-slate-500">{text}</p>
      <p className="mt-4 text-xs text-slate-400">Switch to Inbox to manage emails and drafts.</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 p-10 text-center">
      <h3 className="text-base font-semibold text-slate-900">No emails found</h3>
      <p className="mt-1 text-sm text-slate-500">Try a different filter or sync your inbox.</p>
    </div>
  );
}

export default function InboxPage() {
  const { activeId, syncInbox, dataVersion, refreshData } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<Tab>("Inbox");
  const [filter, setFilter] = useState<Filter>("All Mail");
  const [mobileFilter, setMobileFilter] = useState<MobileFilter>("All");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tone, setTone] = useState<Tone>("Formal");
  const [draftText, setDraftText] = useState("");
  const [draftEditedFor, setDraftEditedFor] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ThreadDetail | null>(null);
  const [priorityOverrides, setPriorityOverrides] = useState<Record<string, Priority>>({});
  const [spammed, setSpammed] = useState<Set<string>>(new Set());
  const [priorityMenu, setPriorityMenu] = useState<string | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<{ threads: ThreadSummary[] }>(`/emails/inbox/${activeId}?limit=100&sort=priority&order=desc`)
      .then((r) => { if (!cancelled) { setThreads(r.threads || []); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoaded(true); });
    get<InboxStats>(`/emails/stats/${activeId}`).then((s) => { if (!cancelled) setStats(s); }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeId, dataVersion]);

  const baseThreads = useMemo(() => threads.filter((t) => !spammed.has(t.id)), [threads, spammed]);
  const effectivePriority = useCallback((t: ThreadSummary): Priority => priorityOverrides[t.id] ?? priorityFromScore(t.priority_score), [priorityOverrides]);

  const filtered = useMemo(() => {
    let list = baseThreads;
    if (activeTab === "Action Items") list = list.filter((t) => t.reply_status === "draft_ready" || t.reply_status === "needs_reply");
    else if (activeTab === "Alerts") list = list.filter((t) => (t.priority_score ?? 0) >= 80 || t.unread > 0);
    if (filter === "Unread") list = list.filter((t) => t.unread > 0);
    else if (filter === "LinkedIn") list = list.filter((t) => senderDisplay(t.last_from).platform === "LinkedIn" || /linkedin/i.test(t.subject || "") || /linkedin/i.test(t.summary || ""));
    else if (filter === "High Priority") list = list.filter((t) => effectivePriority(t) === "High");
    if (mobileFilter === "Categories") list = list.filter((t) => !!t.category);
    else if (mobileFilter === "Action Items") list = list.filter((t) => t.reply_status === "draft_ready" || t.reply_status === "needs_reply");
    else if (mobileFilter === "Friendly") list = list.filter((t) => (t.category || "").includes("client") || (t.category || "").includes("lead"));
    return list;
  }, [baseThreads, activeTab, filter, mobileFilter, effectivePriority]);

  const selected = useMemo(() => {
    if (selectedId && filtered.some((t) => t.id === selectedId)) return filtered.find((t) => t.id === selectedId)!;
    return filtered[0] || baseThreads[0] || null;
  }, [selectedId, filtered, baseThreads]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    get<ThreadDetail>(`/emails/threads/${selected.id}`)
      .then((d) => { if (!cancelled) setSelectedDetail(d); })
      .catch(() => { if (!cancelled) setSelectedDetail(null); });
    return () => { cancelled = true; };
  }, [selected]);

  const detailFor = selectedDetail && selectedDetail.id === selected?.id ? selectedDetail : null;
  const computedDraft = useMemo(() => {
    if (!selected) return "";
    const name = senderDisplay(selected.last_from).name;
    return rewriteDraft(baseDraft(selected, detailFor), tone, name);
  }, [selected, detailFor, tone]);

  const draftEdited = draftEditedFor === selected?.id;
  const shownDraft = draftEdited ? draftText : computedDraft;

  const totalUnread = baseThreads.reduce((a, t) => a + (t.unread || 0), 0) || stats?.unread || 0;
  const highCount = baseThreads.filter((t) => effectivePriority(t) === "High").length;
  const repliesReady = baseThreads.filter((t) => t.reply_status === "draft_ready").length || stats?.pending_drafts || 0;
  const totalEmails = baseThreads.length || stats?.total || 0;

  const kpis = [
    { label: "Total Unread", value: totalUnread, color: "#4F46E5", data: [4, 6, 5, 8, 7, 10, 12, 11, 14, Math.max(totalUnread, 1)] },
    { label: "High Priority", value: highCount, color: "#fb7185", data: [2, 2, 1, 2, 1, 1, 0, 1, 0, Math.max(highCount, 0)] },
    { label: "AI Replies Ready", value: repliesReady, color: "#10B981", data: [0, 0, 1, 1, 1, 2, 1, 2, Math.max(repliesReady, 1), Math.max(repliesReady, 1)] },
    { label: "Total Emails", value: totalEmails, color: "#14b8a6", data: [8, 10, 12, 14, 16, 18, 20, 24, 28, Math.max(totalEmails, 1)] },
  ];

  const onSelect = (id: string) => { setSelectedId(id); };
  const onReply = (id: string) => { onSelect(id); setAssistantOpen(true); };
  const markSpam = async (id: string) => {
    try { await patch(`/emails/threads/${id}`, { category: "spam" }); } catch {}
    setSpammed((s) => new Set([...s, id]));
    setToast("Moved to Spam");
    refreshData();
  };
  const setPriority = async (id: string, p: Priority) => {
    setPriorityMenu(null);
    setPriorityOverrides((m) => ({ ...m, [id]: p }));
    try { await patch(`/emails/threads/${id}`, { priority_score: scoreForPriority(p) }); } catch {}
    setToast(`Priority set to ${p}`);
    refreshData();
  };
  const doSync = async () => {
    if (!activeId || syncing) return;
    setSyncing(true);
    try { await syncInbox(); setToast("Inbox synced"); refreshData(); } catch { setToast("Sync failed"); }
    finally { setSyncing(false); }
  };
  const sendReply = () => { setToast("Reply sent"); setAssistantOpen(false); };
  const onTone = (t: Tone) => { setTone(t); setDraftEditedFor(null); };
  const onDraftChange = (v: string) => { setDraftText(v); setDraftEditedFor(selected?.id ?? null); };

  if (!activeId) return <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-10 text-center text-slate-600">Connect Gmail to start using Smart Inbox.</div>;

  const desktopFilters: Filter[] = ["All Mail", "Unread", "LinkedIn", "High Priority"];
  const mobileFilters: MobileFilter[] = ["All", "Categories", "Action Items", "Friendly"];
  const loading = !loaded && threads.length === 0;

  const content = () => {
    if (activeTab !== "Inbox" && activeTab !== "Action Items" && activeTab !== "Alerts") {
      if (activeTab === "Daily Digest") return <Placeholder title="Daily Digest" text="Your AI-generated daily summary will appear here." />;
      return <Placeholder title="Settings" text="Manage your Smart Inbox preferences here." />;
    }
    if (activeTab === "Alerts" && filtered.length === 0) return <Placeholder title="Alerts" text="No alerts right now. High-priority and unread alerts will appear here." />;
    if (activeTab === "Action Items" && filtered.length === 0) return <Placeholder title="Action Items" text="No action items right now. Emails needing replies will appear here." />;

    const list = activeTab === "Inbox" ? filtered : filtered;

    return (
      <>
        <div className="hidden lg:flex flex-wrap items-center gap-2">
          {TABS.map((t) => (
            <button key={t} onClick={() => setActiveTab(t)} className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${activeTab === t ? "bg-indigo-600 text-white shadow-sm" : "border border-slate-200/80 bg-white/80 text-slate-600 hover:border-indigo-200 hover:text-slate-900"}`}>
              {t}
            </button>
          ))}
        </div>

        <div className="hidden lg:grid grid-cols-2 gap-4">
          {kpis.map((k) => (
            <div key={k.label} className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm">
              <div className="mb-2 text-xs font-medium text-slate-500">{k.label}</div>
              <Sparkline color={k.color} data={k.data} />
              <div className="mt-1 text-2xl font-semibold text-slate-900">{k.value}</div>
            </div>
          ))}
        </div>

        <div className="lg:hidden -mx-1 flex gap-3 overflow-x-auto px-1 pb-1 no-scrollbar">
          {kpis.map((k) => (
            <div key={k.label} className="min-w-[160px] rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-sm">
              <div className="text-[11px] font-medium text-slate-500">{k.label}</div>
              <div className="mt-1 h-8"><svg viewBox="0 0 100 30" className="h-8 w-full" preserveAspectRatio="none"><polyline points={sparkPoints(k.data)} fill="none" stroke={k.color} strokeWidth="3" strokeLinecap="round" /></svg></div>
              <div className="text-xl font-semibold text-slate-900">{k.value}</div>
            </div>
          ))}
        </div>

        <div className="hidden lg:flex flex-wrap items-center gap-2">
          {desktopFilters.map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${filter === f ? "bg-indigo-600 text-white shadow-sm" : "border border-slate-200/80 bg-white/80 text-slate-600 hover:border-indigo-200 hover:text-slate-900"}`}>
              {f}
            </button>
          ))}
        </div>

        <div className="lg:hidden -mx-1 flex gap-2 overflow-x-auto px-1 no-scrollbar">
          {mobileFilters.map((f) => (
            <button key={f} onClick={() => setMobileFilter(f)} className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium ${mobileFilter === f ? "bg-indigo-600 text-white" : "border border-slate-200/80 bg-white/80 text-slate-600"}`}>
              {f}
            </button>
          ))}
        </div>

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        {loading && <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-8 text-center text-sm text-slate-500">Loading inbox…</div>}

        <div className="hidden lg:block space-y-3">
          {!loading && list.length === 0 && <EmptyState />}
          {list.map((t) => {
            const p = effectivePriority(t);
            const sel = selected?.id === t.id;
            return (
              <div key={t.id} onClick={() => onSelect(t.id)} className={`cursor-pointer rounded-2xl border bg-white/90 p-4 shadow-sm transition ${sel ? "border-indigo-300 ring-1 ring-indigo-200" : "border-slate-200/80 hover:border-slate-300"}`}>
                <div className="flex items-start gap-3">
                  <input type="checkbox" className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600" onClick={(e) => e.stopPropagation()} readOnly />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <div className="truncate text-sm font-semibold text-slate-900">{senderDisplay(t.last_from).label}</div>
                      <div className="shrink-0 text-xs text-slate-500">{timeLabel(t.last_activity_at)}</div>
                    </div>
                    <div className="mt-1 text-sm text-slate-600 line-clamp-1">{t.summary || t.subject || "(no summary)"}</div>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <button onClick={(e) => { e.stopPropagation(); onReply(t.id); }} className="inline-flex items-center rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700">Reply</button>
                        <button onClick={(e) => { e.stopPropagation(); void markSpam(t.id); }} className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Mark as Spam</button>
                      </div>
                      <div className="relative">
                        <button onClick={(e) => { e.stopPropagation(); setPriorityMenu((v) => v === t.id ? null : t.id); }} className="inline-flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600">Set Priority <ChevronDown size={14} /></button>
                        {priorityMenu === t.id && (
                          <div className="priority-menu" onClick={(e) => e.stopPropagation()}>
                            {(["High", "Medium", "Low"] as Priority[]).map((opt) => (
                              <button key={opt} onClick={() => void setPriority(t.id, opt)} className={opt === p ? "font-semibold text-indigo-700" : ""}>{opt}</button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="lg:hidden space-y-3 pb-24">
          {!loading && list.length === 0 && <EmptyState />}
          {list.map((t) => (
            <div key={t.id} onClick={() => onSelect(t.id)} className={`rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm ${selected?.id === t.id ? "ring-1 ring-indigo-200" : ""}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-semibold text-slate-900">{senderDisplay(t.last_from).label}</div>
                <div className="text-xs text-slate-500">{timeLabel(t.last_activity_at)}</div>
              </div>
              <div className="mt-1 text-sm leading-5 text-slate-600 line-clamp-3">{t.summary || t.subject || "(no summary)"}</div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <button onClick={(e) => { e.stopPropagation(); onReply(t.id); }} className="rounded-lg bg-indigo-600 px-2 py-2 text-xs font-medium text-white">Reply</button>
                <button onClick={(e) => { e.stopPropagation(); void markSpam(t.id); }} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-medium text-slate-700">Mark as Spam</button>
                <div className="relative">
                  <button onClick={(e) => { e.stopPropagation(); setPriorityMenu((v) => v === t.id ? null : t.id); }} className="w-full rounded-lg bg-emerald-500 px-2 py-2 text-xs font-medium text-white">Set Priority</button>
                  {priorityMenu === t.id && (
                    <div className="priority-menu right-0" onClick={(e) => e.stopPropagation()}>
                      {(["High", "Medium", "Low"] as Priority[]).map((opt) => (
                        <button key={opt} onClick={() => void setPriority(t.id, opt)}>{opt}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="lg:hidden fixed bottom-[76px] left-1/2 z-40 -translate-x-1/2">
          <button onClick={() => setAssistantOpen(true)} className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow-lg shadow-indigo-600/20">
            <Sparkles size={16} /> AI Assistant
          </button>
        </div>

        {assistantOpen && (
          <div className="lg:hidden">
            <div className="sheet-backdrop" onClick={() => setAssistantOpen(false)} />
            <div className="sheet">
              <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-slate-300" />
              <AssistantPanel mobile selected={selected} tone={tone} onTone={onTone} shownDraft={shownDraft} onDraftChange={onDraftChange} onSend={sendReply} onClose={() => setAssistantOpen(false)} />
            </div>
          </div>
        )}
      </>
    );
  };

  return (
    <div className="relative">
      <div className="flex w-full items-start gap-6">
        <section className="min-w-0 flex-1 space-y-4">
          <div className="hidden lg:flex items-center justify-between">
            <div className="text-sm text-slate-500">Smart Inbox overview</div>
            <button onClick={() => void doSync()} disabled={syncing} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60">
              {syncing ? <span className="spin" /> : <SlidersHorizontal size={14} />} {syncing ? "Syncing…" : "Sync Gmail"}
            </button>
          </div>
          {content()}
        </section>

        <aside className="hidden lg:block w-[340px] shrink-0 sticky top-[84px]">
          <div className="rounded-2xl border border-slate-200/80 bg-[#F8FAFC] p-4 shadow-sm">
            <AssistantPanel selected={selected} tone={tone} onTone={onTone} shownDraft={shownDraft} onDraftChange={onDraftChange} onSend={sendReply} onClose={() => {}} />
          </div>
        </aside>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
