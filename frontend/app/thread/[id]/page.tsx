"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CategoryChip, cleanEmailBody, FlagChip, HintChip, ReplyStatusChip, formatDate, formatTime, MoodChip, scoreClass } from "@/lib/format";
import { get, patch, post } from "@/lib/api";
import type { ThreadDetail } from "@/lib/types";
import { DraftBox } from "@/components/draft-box";

const NOISE_CATEGORIES = new Set(["spam", "newsletter"]);

function summarize(body: string): string {
  const text = body.replace(/\s+/g, " ").trim();
  if (!text) return "";
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? [text];
  const summary = sentences.slice(0, 2).join(" ").trim();
  return summary.length > 220 ? `${summary.slice(0, 217).trimEnd()}…` : summary;
}

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [draftingId, setDraftingId] = useState<string | null>(null);
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());
  const openedOnce = useRef(false);

  useEffect(() => {
    if (!thread || openedOnce.current || thread.emails.length === 0) return;
    openedOnce.current = true;
    const sorted = [...thread.emails].sort(
      (a, b) =>
        new Date(a.received_at ?? 0).getTime() -
        new Date(b.received_at ?? 0).getTime(),
    );
    setOpenIds(new Set([sorted[sorted.length - 1].id]));
  }, [thread]);

  const markRead = useCallback(async (emailId: string, read: boolean) => {
    setThread((prev) =>
      prev
        ? {
            ...prev,
            unread: prev.emails.filter((e) =>
              e.id === emailId ? !read : !e.is_read,
            ).length,
            emails: prev.emails.map((e) =>
              e.id === emailId ? { ...e, is_read: read } : e,
            ),
          }
        : prev,
    );
    try {
      await patch(`/emails/${emailId}/read`, { is_read: read });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  function toggleEmail(emailId: string) {
    const opening = !openIds.has(emailId);
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (opening) next.add(emailId);
      else next.delete(emailId);
      return next;
    });
    if (opening) {
      const target = thread?.emails.find((e) => e.id === emailId);
      if (target && !target.is_read) void markRead(emailId, true);
    }
  }

  const reload = useCallback(() => {
    get<ThreadDetail>(`/emails/threads/${id}`)
      .then(setThread)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    get<ThreadDetail>(`/emails/threads/${id}`)
      .then((t) => {
        if (!cancelled) setThread(t);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function setActionStatus(id: string, status: "done" | "cancelled") {
    setBusyAction(id);
    try {
      await patch(`/emails/action-items/${id}`, { status });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyAction(null);
    }
  }

  async function generateDraft(emailId: string) {
    setDraftingId(emailId);
    setError(null);
    try {
      await post(`/emails/${emailId}/draft`);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDraftingId(null);
    }
  }

  if (error) return <div className="error-banner">{error}</div>;
  if (!thread) return <div className="empty">Loading thread…</div>;

  return (
    <div>
      <Link href="/" className="back-link">
        ← Back to inbox
      </Link>
      <div className="page-head" style={{ marginTop: 10 }}>
        <div>
          <h1>{thread.subject || "(no subject)"}</h1>
          <div className="sub">
            {thread.emails.length} emails · {formatTime(thread.last_activity_at)}
          </div>
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <span className={`score ${scoreClass(thread.priority_score)}`}>
            {thread.priority_score ?? "–"}
          </span>
          <CategoryChip category={thread.category} />
          <ReplyStatusChip status={thread.reply_status} />
          {thread.flags?.map((f) => (
            <FlagChip key={f} flag={f} />
          ))}
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
          {thread.pipeline_hints.map((h) => (
            <HintChip key={h} hint={h} />
          ))}
        </div>
      )}

      {[...thread.emails]
        .sort(
          (a, b) =>
            new Date(a.received_at ?? 0).getTime() -
            new Date(b.received_at ?? 0).getTime(),
        )
        .map((email) => {
          const body = cleanEmailBody(email.body);
          const summary = (email.ai_summary || summarize(body)).trim();
          const isNoise = thread.category ? NOISE_CATEGORIES.has(thread.category) : false;
          const open = openIds.has(email.id);
          const sender = email.from_addr || "Unknown sender";
          const initial = (sender.match(/[A-Za-z0-9]/)?.[0] ?? "?").toUpperCase();
          return (
            <div key={email.id} className={`email-card gmail ${open ? "open" : ""}`}>
              <button
                type="button"
                className="email-row"
                aria-expanded={open}
                onClick={() => toggleEmail(email.id)}
              >
                <span className="email-avatar">{initial}</span>
                <span className={`email-sender ${email.is_read ? "" : "unread"}`}>
                  {!email.is_read && <span className="unread-dot" />}
                  {sender}
                </span>
                <span className="email-snippet">{summary || "(no preview)"}</span>
                <span className="time">
                  {formatTime(email.received_at)}
                  {email.has_attachment ? " · attachment" : ""}
                </span>
              </button>

              {open && (
                <div className="email-expanded">
                  <div className="email-expanded-head">
                    <span className="email-to">to {email.to_addr || "me"}</span>
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => void markRead(email.id, !email.is_read)}
                    >
                      {email.is_read ? "Mark unread" : "Mark read"}
                    </button>
                  </div>

                  {summary ? (
                    <div className="ai-box email-summary">
                      <div className="label">
                        {email.ai_summary ? "What this email wants" : "Quick summary"}
                      </div>
                      {summary}
                    </div>
                  ) : null}

                  {body && (
                    <details className="email-original">
                      <summary>Show original email</summary>
                      <div className="body">{body}</div>
                    </details>
                  )}
                  {!body && !summary && <div className="body">(empty)</div>}

                  <div className="badge-row">
                    <MoodChip sentiment={email.sentiment} />
                  </div>

                  {!email.draft && !isNoise && (
                    <div className="draft-actions" style={{ marginTop: 10 }}>
                      <button
                        className="btn"
                        disabled={draftingId === email.id}
                        onClick={() => void generateDraft(email.id)}
                      >
                        {draftingId === email.id ? "Drafting…" : "Generate AI reply"}
                      </button>
                    </div>
                  )}

                  {email.draft && (
                    <DraftBox
                      draft={email.draft}
                      recipient={email.from_addr}
                      onChanged={reload}
                    />
                  )}

                  {email.actions.length > 0 && (
                    <div className="panel">
                      <div className="label">Suggested actions</div>
                      {email.actions.map((a) => (
                        <div key={a.id} className="action-item">
                          <span className={`chip ${a.type === "call" ? "hot" : "warm"}`}>
                            {a.type}
                          </span>
                          <span className="desc">
                            {a.description}
                            {a.contact && <span className="sub"> · {a.contact}</span>}
                          </span>
                          <span className="time">due {formatDate(a.due)}</span>
                          {a.status === "open" ? (
                            <span style={{ display: "flex", gap: 6 }}>
                              <button
                                className="btn"
                                disabled={busyAction === a.id}
                                onClick={() => void setActionStatus(a.id, "done")}
                              >
                                Done
                              </button>
                              <button
                                className="btn"
                                disabled={busyAction === a.id}
                                onClick={() => void setActionStatus(a.id, "cancelled")}
                              >
                                Dismiss
                              </button>
                            </span>
                          ) : (
                            <span className={`chip ${a.status === "done" ? "ok" : "neutral"}`}>
                              {a.status}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
    </div>
  );
}