"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CalendarClock, Sparkles, Tag } from "lucide-react";
import { get } from "@/lib/api";
import {
  CategoryChip, FlagChip, HintChip, MoodChip, ReplyStatusChip, ScorePill,
  cleanEmailBody, formatDateTime,
} from "@/lib/format";
import type { ThreadDetail } from "@/lib/types";
import { DraftBox } from "@/components/draft-box";

function sender(from: string | null | undefined) {
  const raw = (from || "Unknown").trim();
  if (raw.includes("<")) return raw.split("<")[0].trim().replace(/"/g, "") || raw;
  return raw.split("@")[0] || raw;
}

export default function ThreadPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try { setThread(await get<ThreadDetail>(`/emails/threads/${id}`)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  if (error) return <div className="stack"><Link href="/" className="back-link"><ArrowLeft size={14} /> Back to inbox</Link><div className="error-banner">{error}</div></div>;
  if (!thread) return <div className="card card-pad sub">Loading conversation…</div>;

  const actions = thread.emails.flatMap((e) => e.actions || []);
  const latestEmail = thread.emails[thread.emails.length - 1];
  const latestDraft = [...thread.emails].reverse().find((e) => e.draft)?.draft || null;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <Link href="/" className="back-link row" style={{ width: "fit-content" }}><ArrowLeft size={14} /> Back to inbox</Link>

      <div className="card card-pad ai-brief">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ minWidth: 0 }}>
            <div className="label">Conversation brief</div>
            <h1 style={{ margin: "0 0 4px", fontSize: 22, letterSpacing: "-.02em" }}>{thread.subject || "(no subject)"}</h1>
            <div className="sub">{thread.email_count} messages · Last activity {formatDateTime(thread.last_activity_at)}</div>
          </div>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <ScorePill score={thread.priority_score} />
            <CategoryChip category={thread.category} />
            <ReplyStatusChip status={thread.reply_status} />
          </div>
        </div>
        {thread.summary && <p style={{ margin: "12px 0 0", fontSize: 14, lineHeight: 1.65, color: "var(--ink-soft)" }}>{thread.summary}</p>}
        <div className="row" style={{ flexWrap: "wrap", marginTop: 10 }}>
          {(thread.flags || []).map((f) => <FlagChip key={f} flag={f} />)}
          {(thread.pipeline_hints || []).map((h) => <HintChip key={h} hint={h} />)}
        </div>
        {thread.flags?.length ? <div className="brief-reason"><strong>Why prioritized:</strong> {thread.flags.map((f) => f.replace(/_/g, " ")).join(", ")}.</div> : null}
      </div>

      <div className="grid-3">
        <div className="panel" style={{ gridColumn: "span 2" }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Messages</h3><span className="sub">Oldest to newest</span>
          </div>
          <div className="email-list">
            {thread.emails.map((e) => (
              <div key={e.id} className="email-card">
                <div className="email-head">
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{sender(e.from_addr)}</div>
                    <div className="meta-line">To: {e.to_addr}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="meta-line">{formatDateTime(e.received_at)}</div>
                    <div className="row" style={{ justifyContent: "flex-end", marginTop: 4 }}>{e.sentiment && <MoodChip sentiment={e.sentiment} />}{e.has_attachment && <span className="chip neutral">Attachment</span>}</div>
                  </div>
                </div>
                {e.ai_summary && <div className="reply-preview" style={{ margin: "8px 0" }}><strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--primary)" }}>AI summary</strong><div style={{ marginTop: 4 }}>{e.ai_summary}</div></div>}
                <div className="body">{cleanEmailBody(e.body) || "(no body content)"}</div>
                {e.draft && <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}><DraftBox draft={e.draft} recipient={e.from_addr} onChanged={() => void load()} /></div>}
              </div>
            ))}
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <h3 className="row" style={{ gap: 8 }}><Sparkles size={16} color="var(--primary)" /> Draft reply</h3>
            {latestDraft ? <DraftBox draft={latestDraft} recipient={latestEmail?.from_addr || ""} onChanged={() => void load()} /> : <div className="sub">No draft yet. Run AI processing to generate a suggested reply.</div>}
          </div>
          <div className="panel">
            <h3 className="row" style={{ gap: 8 }}><CalendarClock size={16} color="var(--warn)" /> Extracted actions</h3>
            {actions.length === 0 ? <div className="sub">No action items extracted for this thread.</div> : (
              <div className="stack" style={{ gap: 8 }}>
                {actions.map((a) => (
                  <div key={a.id} style={{ padding: 10, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-muted)" }}>
                    <div className="row" style={{ justifyContent: "space-between" }}><span className="chip warn">{a.type}</span><span className="sub">{a.status}</span></div>
                    <div style={{ fontSize: 13.5, marginTop: 6 }}>{a.description}</div>
                    <div className="sub" style={{ marginTop: 4 }}>{[a.due && `Due ${formatDateTime(a.due)}`, a.contact, a.property].filter(Boolean).join(" · ")}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="panel">
            <h3 className="row" style={{ gap: 8 }}><Tag size={16} /> Context</h3>
            <div className="kv">
              <div className="k">From</div><div style={{ wordBreak: "break-all" }}>{thread.last_from || "—"}</div>
              <div className="k">Category</div><div>{thread.category || "Uncategorized"}</div>
              <div className="k">Priority</div><div>{thread.priority_score ?? "—"}</div>
              <div className="k">Reply status</div><div>{thread.reply_status || "—"}</div>
              <div className="k">Messages</div><div>{thread.email_count}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
