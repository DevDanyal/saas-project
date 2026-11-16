"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CategoryChip, FlagChip, HintChip, ReplyStatusChip, formatDate, formatTime, MoodChip, scoreClass } from "@/lib/format";
import { get, patch, post } from "@/lib/api";
import type { Draft, ThreadDetail } from "@/lib/types";
import { DraftBox } from "@/components/draft-box";

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [busyRead, setBusyRead] = useState(false);
  const [genBusy, setGenBusy] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const reload = useCallback(() => {
    get<ThreadDetail>(`/emails/threads/${id}`)
      .then(setThread)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    get<ThreadDetail>(`/emails/threads/${id}`)
      .then((t) => { if (!cancelled) setThread(t); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [id]);

  async function setActionStatus(actionId: string, status: "done" | "cancelled") {
    setBusyAction(actionId);
    try {
      await patch(`/emails/action-items/${actionId}`, { status });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyAction(null);
    }
  }

  async function markAll(read: boolean) {
    if (!thread) return;
    setBusyRead(true);
    setError(null);
    try {
      const targets = thread.emails.filter((e) => e.is_read !== read);
      await Promise.all(targets.map((e) => patch(`/emails/${e.id}/read`, { is_read: read })));
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyRead(false);
    }
  }

  async function toggleEmailRead(emailId: string, read: boolean) {
    try {
      await patch(`/emails/${emailId}/read`, { is_read: read });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function generateDraft(emailId: string) {
    setGenBusy(emailId);
    setError(null);
    try {
      await post<Draft>(`/emails/${emailId}/draft`);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenBusy(null);
    }
  }

  if (error) return <div className="error-banner">{error}</div>;
  if (!thread) return <div className="empty">Loading thread...</div>;

  const hasUnread = thread.emails.some((e) => !e.is_read);

  return (
    <div>
      <Link href="/" className="back-link">← Back to inbox</Link>
      <div className="page-head" style={{ marginTop: 10 }}>
        <div>
          <h1>{thread.subject || "(no subject)"}</h1>
          <div className="sub">
            {thread.emails.length} emails · {formatTime(thread.last_activity_at)} · {thread.unread || 0} unread
          </div>
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
          <span className={`score ${scoreClass(thread.priority_score)}`}>{thread.priority_score ?? "-"}</span>
          <CategoryChip category={thread.category} />
          <ReplyStatusChip status={thread.reply_status} />
          {thread.flags?.map((f) => <FlagChip key={f} flag={f} />)}
          <button className="btn" onClick={() => void markAll(!hasUnread)} disabled={busyRead}>
            {busyRead ? "Updating..." : hasUnread ? "Mark all read" : "Mark all unread"}
          </button>
        </div>
      </div>

      {thread.summary && (
        <div className="ai-box" style={{ marginBottom: 4 }}>
          <div className="label">AI summary</div>
          {thread.summary}
        </div>
      )}

      {thread.pipeline_hints?.length > 0 && (
        <div className="badge-row" style={{ marginBottom: 8 }}>
          {thread.pipeline_hints.map((h) => <HintChip key={h} hint={h} />)}
        </div>
      )}

      {[...thread.emails]
        .sort((a, b) => new Date(a.received_at ?? 0).getTime() - new Date(b.received_at ?? 0).getTime())
        .map((email) => {
          const shortSummary = (email.ai_summary || (email.body || "").replace(/\s+/g, " ").trim()).slice(0, 260) || "(no summary available)";
          const showFull = !!expanded[email.id];
          return (
          <div key={email.id} className={`email-card ${email.is_read ? "" : "unread-email"}`} style={!email.is_read ? { borderLeft: "3px solid var(--primary, #a97c2c)" } : undefined}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span className="from" style={{ fontWeight: email.is_read ? 500 : 700 }}>{email.from_addr}</span>
              <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                <span className="time">
                  {formatTime(email.received_at)}{email.has_attachment ? " · attachment" : ""}{!email.is_read ? " · unread" : ""}
                </span>
                <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => void toggleEmailRead(email.id, !email.is_read)}>
                  {email.is_read ? "Mark unread" : "Mark read"}
                </button>
              </span>
            </div>
            <div className="body summary-clamp">{showFull ? (email.body || "(empty)") : shortSummary}{!showFull && shortSummary.length >= 260 ? "..." : ""}</div>
            <button className="btn" style={{ marginTop: 6, padding: "2px 8px", fontSize: 12 }} onClick={() => setExpanded((p) => ({ ...p, [email.id]: !p[email.id] }))}>
              {showFull ? "Show short summary" : "Show original email"}
            </button>
            <div className="badge-row">
              <MoodChip sentiment={email.sentiment} />
            </div>

            {email.draft ? (
              <DraftBox draft={email.draft} recipient={email.from_addr} onChanged={reload} />
            ) : (
              <div style={{ marginTop: 10 }}>
                <button className="btn primary" onClick={() => void generateDraft(email.id)} disabled={genBusy === email.id}>
                  {genBusy === email.id ? "Generating AI reply..." : "Generate AI reply"}
                </button>
              </div>
            )}

            {email.actions.length > 0 && (
              <div className="panel">
                <div className="label">Suggested actions</div>
                {email.actions.map((a) => (
                  <div key={a.id} className="action-item">
                    <span className={`chip ${a.type === "call" ? "hot" : "warm"}`}>{a.type}</span>
                    <span className="desc">
                      {a.description}
                      {a.contact && <span className="sub"> · {a.contact}</span>}
                    </span>
                    <span className="time">due {formatDate(a.due)}</span>
                    {a.status === "open" ? (
                      <span style={{ display: "flex", gap: 6 }}>
                        <button className="btn" disabled={busyAction === a.id} onClick={() => void setActionStatus(a.id, "done")}>Done</button>
                        <button className="btn" disabled={busyAction === a.id} onClick={() => void setActionStatus(a.id, "cancelled")}>Dismiss</button>
                      </span>
                    ) : (
                      <span className={`chip ${a.status === "done" ? "ok" : "neutral"}`}>{a.status}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );})}
    </div>
  );
}
