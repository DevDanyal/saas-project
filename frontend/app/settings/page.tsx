"use client";

import { useEffect, useState } from "react";
import { get, put } from "@/lib/api";
import type { Preferences } from "@/lib/types";
import { useUser } from "@/lib/user-context";

type Form = { style: string; signature: string; notes: string; rules: string; autopilot: boolean; confidence: number };
const EMPTY: Form = { style: "friendly", signature: "", notes: "", rules: "", autopilot: false, confidence: 0.9 };

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
          signature: typeof tone.signature === "string" ? tone.signature : "",
          notes: typeof tone.notes === "string" ? tone.notes : "",
          rules: p.rules ?? "",
          autopilot: Boolean(p.auto_features?.autopilot),
          confidence: typeof p.auto_features?.autopilot_confidence === "number" ? p.auto_features.autopilot_confidence : 0.9,
        });
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [activeId]);

  function update<K extends keyof Form>(key: K, value: Form[K]) { setForm((f) => ({ ...f, [key]: value })); setSaved(false); }

  async function save() {
    if (!activeId) return;
    setSaving(true); setError(null); setSaved(false);
    try {
      await put<Preferences>(`/preferences/${activeId}`, {
        tone_profile: { style: form.style, signature: form.signature, notes: form.notes },
        rules: form.rules, autopilot: form.autopilot, autopilot_confidence: form.confidence,
      });
      setSaved(true);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  }

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Select an account to edit preferences.</p></div>;
  if (loading) return <div className="card card-pad sub">Loading settings…</div>;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>AI Settings</h1>
          <div className="sub">Control tone, guardrails, and automation so replies stay on-brand and safe.</div>
        </div>
        <button className="btn primary" onClick={() => void save()} disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {saved && <div className="notice-banner">Settings saved.</div>}

      <div className="grid-2">
        <div className="card card-pad stack">
          <div><div className="label">Reply tone</div>
            <select className="select" value={form.style} onChange={(e) => update("style", e.target.value)}>
              <option value="friendly">Friendly</option><option value="professional">Professional</option><option value="formal">Formal</option><option value="casual">Casual</option><option value="concise">Concise</option>
            </select></div>
          <div><div className="label">Signature</div>
            <textarea className="textarea" rows={3} placeholder={"Best,\nDana Realtor · 555-0100"} value={form.signature} onChange={(e) => update("signature", e.target.value)} /></div>
          <div><div className="label">Voice notes</div>
            <textarea className="textarea" rows={4} placeholder="Short sentences, no emojis, always offer two time slots." value={form.notes} onChange={(e) => update("notes", e.target.value)} /></div>
        </div>

        <div className="card card-pad stack">
          <div><div className="label">Hard rules & guardrails</div>
            <textarea className="textarea" rows={5} placeholder="Never quote prices or promise financing. Escalate legal questions. Always confirm availability." value={form.rules} onChange={(e) => update("rules", e.target.value)} />
            <div className="sub" style={{ marginTop: 6 }}>These rules guide drafts and autopilot decisions.</div></div>
          <div className="card card-pad" style={{ background: "var(--surface-muted)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <div><div style={{ fontWeight: 700 }}>Auto-Pilot</div><div className="sub">Automatically send low-risk replies that meet your confidence threshold. Sensitive emails are always held for review.</div></div>
              <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={form.autopilot} onChange={(e) => update("autopilot", e.target.checked)} /> <span style={{ fontSize: 13, fontWeight: 600 }}>{form.autopilot ? "On" : "Off"}</span></label>
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="label" style={{ marginBottom: 4 }}>Confidence threshold · {Math.round(form.confidence * 100)}%</div>
              <input type="range" min={0.5} max={0.99} step={0.01} value={form.confidence} onChange={(e) => update("confidence", Number(e.target.value))} style={{ width: "100%" }} />
              <div className="sub">Higher = safer (fewer auto-sends). Lower = more automation.</div>
            </div>
          </div>
          <div><button className="btn primary" onClick={() => void save()} disabled={saving}>{saving ? "Saving…" : "Save settings"}</button></div>
        </div>
      </div>
    </div>
  );
}
