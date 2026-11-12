"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  CategoryChip,
  FlagChip,
  HintChip,
  ReplyStatusChip,
  formatTime,
  scoreClass,
} from "@/lib/format";
import { get } from "@/lib/api";
import type { InboxStats, ThreadSummary } from "@/lib/types";
import { useUser } from "@/lib/user-context";

const SECTIONS: { key: string; label: string }[] = [
  { key: "", label: "All Mail" },
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

type SortKey = "priority" | "recent" | "subject";
type RunState = "idle" | "syncing" | "analyzing";

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

function briefFor(stats: InboxStats): string {
  if (stats.total === 0)
    return "No emails yet. Run the assistant to fetch and review your Gmail inbox.";
  if (stats.unprocessed > 0)
    return `You have ${plural(stats.customers, "customer")}, ${plural(
      stats.leads,
      "lead",
    )}, and ${plural(stats.unprocessed, "conversation")} not reviewed yet.`;
  const attention =
    stats.attention > 0
      ? `${plural(stats.attention, "conversation")} need your attention.`
      : "Nothing urgent right now.";
  return `You have ${plural(stats.customers, "customer")} and ${plural(
    stats.leads,
    "lead",
  )}. ${attention} ${
    stats.pending_drafts > 0
      ? `${plural(stats.pending_drafts, "reply", "replies")} waiting for approval.`
      : ""
  }`.trim();
}

export default function InboxPage() {
  const { activeId, syncInbox, processAll, dataVersion } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");

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
    if (category) params.set("category", category);
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
  }, [
    activeId,
    debouncedQuery,
    category,
    flag,
    minPriority,
    sort,
    order,
    dataVersion,
  ]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<InboxStats>(`/emails/stats/${activeId}`)
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch(() => {
        /* the threads request surfaces errors */
      });
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
    } catch {
      /* keep going: review whatever is already synced */
    }
    setRunState("analyzing");
    try {
      const p = await processAll();
      const parts = [];
      if (newEmails) parts.push(`${plural(newEmails, "new email")} synced`);
      parts.push(`${plural(p.processed, "email")} reviewed`);
      if (p.errors) parts.push(`${p.errors} error(s)`);
      setNotice(parts.join(" · "));
    } catch {
      /* error surfaced in banner */
    } finally {
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

  const sectionCount = (key: string) =>
    key === "" ? (stats?.total ?? 0) : (stats?.categories?.[key] ?? 0);
  const sectionLabel =
    SECTIONS.find((s) => s.key === category)?.label ?? "All Mail";

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Inbox</h1>
          <div className="sub">Your AI-assessed inbox at a glance.</div>
        </div>
      </div>

      <div className="assistant-brief">
        <div>
          <div className="label">Inbox assistant</div>
          <p>{stats ? briefFor(stats) : "Reading your inbox…"}</p>
          {notice && <div className="assistant-note">{notice}</div>}
        </div>
        <button
          className="btn primary"
          onClick={() => void runAssistant()}
          disabled={runState !== "idle"}
        >
          {runState !== "idle" && <span className="spin" />}
          {runState === "syncing"
            ? "Syncing Gmail…"
            : runState === "analyzing"
              ? "Reviewing emails…"
              : "Run Assistant"}
        </button>
      </div>

      <div className="section-tabs" role="tablist" aria-label="Inbox sections">
        {SECTIONS.map((s) => (
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

      <div className="toolbar">
        <input
          className="tool-input"
          placeholder="Search subject or summary…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="tool-select"
          value={flag}
          onChange={(e) => setFlag(e.target.value)}
          aria-label="Flag"
        >
          <option value="">All flags</option>
          {FLAGS.map((f) => (
            <option key={f} value={f}>
              {f.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select
          className="tool-select"
          value={minPriority}
          onChange={(e) => setMinPriority(e.target.value)}
          aria-label="Minimum priority"
        >
          <option value="">Any priority</option>
          <option value="80">80+</option>
          <option value="60">60+</option>
          <option value="40">40+</option>
        </select>
        <select
          className="tool-select"
          value={`${sort}:${order}`}
          onChange={(e) => {
            const [s, o] = e.target.value.split(":") as [SortKey, "asc" | "desc"];
            setSort(s);
            setOrder(o);
          }}
          aria-label="Sort"
        >
          <option value="priority:desc">Priority high → low</option>
          <option value="priority:asc">Priority low → high</option>
          <option value="recent:desc">Newest first</option>
          <option value="recent:asc">Oldest first</option>
          <option value="subject:asc">Subject A → Z</option>
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {threads === null && <div className="empty">Loading inbox…</div>}
      {threads !== null && threads.length === 0 && (
        <div className="empty">
          <h2>No threads in {sectionLabel}</h2>
          <p>
            {stats && stats.total === 0
              ? "Press “Run Assistant” to fetch and review your Gmail inbox."
              : "Try another section, clear the filters, or run the assistant again."}
          </p>
        </div>
      )}

      {threads !== null && threads.length > 0 && (
        <div className="thread-list">
          {threads.map((t) => (
            <Link key={t.id} href={`/thread/${t.id}`} className="thread-row">
              <div className="row-top">
                <span className={`score ${scoreClass(t.priority_score)}`}>
                  {t.priority_score ?? "–"}
                </span>
                <span className="subject">{t.subject || "(no subject)"}</span>
                <CategoryChip category={t.category} />
                <ReplyStatusChip status={t.reply_status} />
                {t.flags?.slice(0, 2).map((f) => (
                  <FlagChip key={f} flag={f} />
                ))}
              </div>
              <div className="meta">
                <span>{plural(t.emails, "email")}</span>
                {t.last_from && (
                  <>
                    <span>·</span>
                    <span className="from">from {t.last_from}</span>
                  </>
                )}
                <span>·</span>
                <span>{formatTime(t.last_activity_at)}</span>
              </div>
              {t.pipeline_hints?.length > 0 && (
                <div className="badge-row">
                  {t.pipeline_hints.slice(0, 3).map((h) => (
                    <HintChip key={h} hint={h} />
                  ))}
                </div>
              )}
              {t.summary && <div className="summary">{t.summary}</div>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
