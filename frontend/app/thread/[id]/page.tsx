"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CategoryChip, FlagChip, HintChip, formatDate, formatTime, MoodChip, scoreClass } from "@/lib/format";
import { get } from "@/lib/api";
import type { ThreadDetail } from "@/lib/types";
import { DraftBox } from "@/components/draft-box";

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        .map((email) => (
          <div key={email.id} className="email-card">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="from">{email.from_addr}</span>
              <span className="time">
                {formatTime(email.received_at)}
                {email.has_attachment ? " · attachment" : ""}
              </span>
            </div>
            <div className="body">{email.body || email.ai_summary || "(empty)"}</div>
            <div className="badge-row">
              <MoodChip sentiment={email.sentiment} />
              {email.ai_summary && (
                <span className="chip neutral">summary: {email.ai_summary}</span>
              )}
            </div>

            {email.draft && <DraftBox draft={email.draft} onSent={reload} />}

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
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
    </div>
  );
}