"use client";

import { useEffect, useRef, useState } from "react";

import { patch, post } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Draft } from "@/lib/types";

type SendResult = {
  draft_id: string;
  status: string;
  sent_message_id: string | null;
  to?: string;
};

export function DraftBox({
  draft,
  recipient,
  onChanged,
}: {
  draft: Draft;
  recipient: string;
  onChanged: () => void;
}) {
  const sent = draft.status === "sent";
  const rejected = draft.status === "rejected";
  const [text, setText] = useState(draft.text);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const dirty = text.trim() !== draft.text.trim();

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const send = () =>
    run(() => post<SendResult>(`/emails/drafts/${draft.id}/send`, { text }));
  const save = () => run(() => patch(`/emails/drafts/${draft.id}`, { text }));
  const reject = () => run(() => post(`/emails/drafts/${draft.id}/reject`));

  if (sent) {
    return (
      <div className="ai-box" style={{ marginTop: 12 }}>
        <div className="label">
          Reply sent {draft.sent_at && <span>· {formatTime(draft.sent_at)}</span>}
        </div>
        <div className="sent-line">
          <span className="chip ok">Replied to {recipient}</span>
        </div>
        <div className="body" style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
          {draft.text}
        </div>
      </div>
    );
  }

  if (rejected) {
    return (
      <div className="ai-box" style={{ marginTop: 12 }}>
        <div className="label">AI draft reply · skipped</div>
        <div className="auto-note">
          <span className="chip neutral">No reply sent to {recipient}</span>
        </div>
        <div className="body muted" style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
          {draft.text}
        </div>
      </div>
    );
  }

  return (
    <div className="ai-box" style={{ marginTop: 12 }}>
      <div className="label">
        AI draft reply {draft.tone && <span>· tone: {draft.tone}</span>}
      </div>

      {!editing ? (
        <>
          <div className="reply-preview">{draft.text}</div>
          <div className="draft-question">
            Send this reply to {recipient}?
          </div>
        </>
      ) : (
        <textarea
          ref={inputRef}
          className="draft-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={Math.min(12, Math.max(4, text.split("\n").length + 1))}
        />
      )}

      {draft.auto_decision && !editing && (
        <div className="auto-note">
          <span className={`chip ${draft.auto_decision.send ? "ok" : "warm"}`}>
            {draft.auto_decision.send
              ? `Auto-Pilot approved · ${Math.round(
                  draft.auto_decision.confidence * 100,
                )}%`
              : "Held for your review"}
          </span>
          {draft.auto_decision.reason && (
            <span className="sub"> {draft.auto_decision.reason}</span>
          )}
        </div>
      )}

      {error && (
        <div className="error-banner" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}

      {!editing ? (
        <div className="draft-actions">
          <button
            className="btn primary"
            onClick={send}
            disabled={busy || !draft.text.trim()}
          >
            {busy ? "Sending…" : "Yes, send reply"}
          </button>
          <button className="btn" onClick={() => { setText(draft.text); setEditing(true); }} disabled={busy}>
            Edit draft
          </button>
          <button className="btn danger" onClick={reject} disabled={busy}>
            No, skip
          </button>
        </div>
      ) : (
        <div className="draft-actions">
          <button
            className="btn primary"
            onClick={send}
            disabled={busy || !text.trim()}
          >
            {busy ? "Sending…" : dirty ? "Send my reply" : "Send reply"}
          </button>
          <button
            className="btn"
            onClick={() => {
              void save();
              setEditing(false);
            }}
            disabled={busy || !dirty}
          >
            Save & close
          </button>
          <button
            className="btn"
            onClick={() => {
              setText(draft.text);
              setEditing(false);
            }}
            disabled={busy}
          >
            Use AI draft
          </button>
        </div>
      )}
    </div>
  );
}
