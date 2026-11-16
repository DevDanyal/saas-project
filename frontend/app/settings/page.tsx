"use client";

import { useEffect, useState } from "react";

import { get, put } from "@/lib/api";
import type { Preferences } from "@/lib/types";
import { useUser } from "@/lib/user-context";

type Form = {
  style: string;
  signature: string;
  notes: string;
  rules: string;
  autopilot: boolean;
  confidence: number;
};

const EMPTY: Form = {
  style: "friendly",
  signature: "",
  notes: "",
  rules: "",
  autopilot: false,
  confidence: 0.9,
};

export default function SettingsPage() {
  const { activeId } = useUser();
  const [form, setForm] = useState<Form>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const p = await get<Preferences>(`/preferences/${activeId}`);
        if (cancelled) return;
        const tone = (p.tone_profile ?? {}) as Record<string, unknown>;
        setForm({
          style: typeof tone.style === "string" ? tone.style : "friendly",
          signature:
            typeof tone.signature === "string" ? tone.signature : "",
          notes: typeof tone.notes === "string" ? tone.notes : "",
          rules: p.rules ?? "",
          autopilot: Boolean(p.auto_features?.autopilot),
          confidence:
            typeof p.auto_features?.autopilot_confidence === "number"
              ? p.auto_features.autopilot_confidence
              : 0.9,
        });
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(false);
  }

  async function save() {
    if (!activeId) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await put<Preferences>(`/preferences/${activeId}`, {
        tone_profile: {
          style: form.style,
          signature: form.signature,
          notes: form.notes,
        },
        rules: form.rules,
        autopilot: form.autopilot,
        autopilot_confidence: form.confidence,
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account</h2>
        <p>Select an account to edit its AI preferences.</p>
      </div>
    );

  if (loading) return <div className="empty">Loading settings...</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>AI Settings</h1>
          <div className="sub">
            Train the assistant on your voice and guardrails.
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ display: "grid", gap: 14 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span className="label">Reply tone</span>
          <select
            className="tool-select"
            value={form.style}
            onChange={(e) => update("style", e.target.value)}
          >
            <option value="friendly">Friendly</option>
            <option value="professional">Professional</option>
            <option value="formal">Formal</option>
            <option value="casual">Casual</option>
            <option value="concise">Concise</option>
          </select>
        </label>

        <label style={{ display: "grid", gap: 6 }}>
          <span className="label">Signature</span>
          <textarea
            className="draft-input"
            rows={3}
            placeholder="Best,&#10;Dana Realtor · 555-0100"
            value={form.signature}
            onChange={(e) => update("signature", e.target.value)}
          />
        </label>

        <label style={{ display: "grid", gap: 6 }}>
          <span className="label">Voice notes</span>
          <textarea
            className="draft-input"
            rows={3}
            placeholder="Short sentences, no emojis, always offer two time slots."
            value={form.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </label>

        <label style={{ display: "grid", gap: 6 }}>
          <span className="label">Hard rules</span>
          <textarea
            className="draft-input"
            rows={3}
            placeholder="Never quote prices or promise financing. Escalate legal questions."
            value={form.rules}
            onChange={(e) => update("rules", e.target.value)}
          />
        </label>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            id="autopilot"
            type="checkbox"
            checked={form.autopilot}
            onChange={(e) => update("autopilot", e.target.checked)}
          />
          <label htmlFor="autopilot">
            Auto-Pilot: send low-risk replies automatically
          </label>
        </div>

        <label style={{ display: "grid", gap: 6 }}>
          <span className="label">
            Auto-Pilot confidence threshold · {Math.round(form.confidence * 100)}%
          </span>
          <input
            type="range"
            min={0.5}
            max={0.99}
            step={0.01}
            value={form.confidence}
            onChange={(e) => update("confidence", Number(e.target.value))}
          />
        </label>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button className="btn primary" onClick={() => void save()} disabled={saving}>
            {saving ? "Saving..." : "Save settings"}
          </button>
          {saved && <span className="chip ok">Saved</span>}
        </div>
      </div>
    </div>
  );
}
