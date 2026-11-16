"use client";

import { useState } from "react";
import { ApiError, post } from "@/lib/api";
import type { User } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { Mail, ShieldCheck } from "lucide-react";

type Mode = "signin" | "signup";

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
      <path fill="#34A853" d="M9 18c2.45 0 4.5-.81 6-2.19l-2.92-2.26c-.81.54-1.84.86-3.08.86-2.37 0-4.38-1.6-5.1-3.75H1.87v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.9 10.66a5.4 5.4 0 0 1 0-3.44V4.9H1.87a9 9 0 0 0 0 8.09l2.03-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.33 0 2.53.46 3.47 1.35l2.59-2.59C13.5.98 11.45 0 9 0A9 9 0 0 0 1.87 4.9l2.03 2.32C4.62 5.07 6.63 3.58 9 3.58z" />
    </svg>
  );
}

export function AuthScreen() {
  const { connectGmail, refreshUser } = useUser();
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail.includes("@")) { setError("Enter a valid email address."); return; }
    if (!password) { setError("Enter your password."); return; }
    if (mode === "signup" && password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setBusy(true); setError(null);
    try {
      if (mode === "signup") await post<User>("/auth/signup", { name: name.trim() || "Agent", email: cleanEmail, password });
      else await post<User>("/auth/login", { email: cleanEmail, password });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
      setBusy(false); return;
    }
    try {
      const me = await refreshUser();
      if (me && !me.gmail_connected && /@(gmail|googlemail)\.com$/i.test(cleanEmail)) {
        try { await connectGmail(); return; } catch {}
      }
    } catch {
      setError("Signed in, but session could not be confirmed. Refresh and try again.");
    }
    setBusy(false);
  }

  async function handleGoogle() {
    if (busy) return;
    setBusy(true); setError(null);
    try { await connectGmail(); } catch { setError("Could not start Google sign-in."); setBusy(false); }
  }

  return (
    <div className="app-bg" style={{ minHeight: "100dvh", display: "grid", gridTemplateColumns: "1fr", alignItems: "stretch" }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.1fr) minmax(340px,480px)", minHeight: "100dvh" }} className="auth-grid">
        <section style={{ padding: "48px clamp(20px,5vw,64px)", display: "flex", flexDirection: "column", justifyContent: "center", gap: 24 }}>
          <div className="row" style={{ gap: 10 }}><span className="brand-mark"><Mail size={16} /></span><strong>Smart Inbox</strong></div>
          <div>
            <h1 style={{ fontSize: "clamp(28px,4vw,44px)", lineHeight: 1.1, letterSpacing: "-.03em", margin: "0 0 10px", fontWeight: 750 }}>Turn 100 emails into one clear action plan.</h1>
            <p className="sub" style={{ fontSize: 16, maxWidth: 560 }}>An AI workspace for real estate agents that prioritizes hot leads, extracts tasks, and drafts replies you can trust and send in seconds.</p>
          </div>
          <div className="grid-2" style={{ maxWidth: 560 }}>
            {[ ["Prioritized triage","Hot leads, deadlines, and complaints surfaced with reasons."], ["Drafts in your voice","Review, edit, and send replies with full control."], ["Action extraction","Calls, follow-ups, and tasks captured automatically."], ["Daily brief","A morning digest of what needs attention now."] ].map(([t,d]) => (
              <div key={t} className="card card-pad"><div style={{ fontWeight: 700, fontSize: 14 }}>{t}</div><div className="sub">{d}</div></div>
            ))}
          </div>
          <div className="row sub"><ShieldCheck size={16} color="var(--primary)" /> Secure OAuth connection. Drafts never send without your action.</div>
        </section>

        <section style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "32px 20px", background: "rgba(255,255,255,.55)", borderLeft: "1px solid var(--border)" }}>
          <div className="card" style={{ width: "100%", maxWidth: 400, padding: 24 }}>
            <h2 style={{ margin: "0 0 4px", fontSize: 20, letterSpacing: "-.02em" }}>{mode === "signin" ? "Sign in" : "Create your account"}</h2>
            <p className="sub" style={{ margin: "0 0 16px" }}>{mode === "signin" ? "Welcome back. Pick up where you left off." : "Start with email and connect Gmail in one flow."}</p>
            <button type="button" onClick={() => void handleGoogle()} disabled={busy} className="btn" style={{ width: "100%", justifyContent: "center", marginBottom: 12 }}>
              <GoogleMark /> Continue with Google
            </button>
            <div className="row" style={{ margin: "12px 0" }}><span style={{ flex: 1, height: 1, background: "var(--border)" }} /><span className="sub" style={{ fontSize: 11 }}>OR</span><span style={{ flex: 1, height: 1, background: "var(--border)" }} /></div>
            <form onSubmit={(e) => void handleSubmit(e)} className="stack" style={{ gap: 10 }}>
              {mode === "signup" && (
                <label className="stack" style={{ gap: 4 }}><span className="label" style={{ margin: 0 }}>Name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jordan Reeves" autoComplete="name" disabled={busy} /></label>
              )}
              <label className="stack" style={{ gap: 4 }}><span className="label" style={{ margin: 0 }}>Email</span><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@agency.com" autoComplete="email" required disabled={busy} /></label>
              <label className="stack" style={{ gap: 4 }}><span className="label" style={{ margin: 0 }}>Password</span><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete={mode === "signin" ? "current-password" : "new-password"} required disabled={busy} /></label>
              {error && <div className="error-banner" role="alert">{error}</div>}
              <button type="submit" disabled={busy} className="btn primary" style={{ width: "100%", marginTop: 2 }}>{busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}</button>
            </form>
            <p className="sub" style={{ marginTop: 12, textAlign: "center" }}>
              {mode === "signin" ? "No account yet?" : "Already have an account?"} {" "}
              <button type="button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null); }} style={{ background: "none", border: 0, color: "var(--primary)", fontWeight: 700, padding: 0 }}>{mode === "signin" ? "Create one" : "Sign in"}</button>
            </p>
          </div>
        </section>
      </div>
      <style>{`@media(max-width:900px){.auth-grid{grid-template-columns:1fr !important}.auth-grid>section:first-child{display:none !important}.auth-grid>section:last-child{border-left:0 !important;background:transparent !important}}`}</style>
    </div>
  );
}
