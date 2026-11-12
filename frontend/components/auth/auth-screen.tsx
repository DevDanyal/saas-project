"use client";

import { useState } from "react";

import { ApiError, post } from "@/lib/api";
import type { User } from "@/lib/types";
import { useUser } from "@/lib/user-context";

type Mode = "signin" | "signup";

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.45 0 4.5-.81 6-2.19l-2.92-2.26c-.81.54-1.84.86-3.08.86-2.37 0-4.38-1.6-5.1-3.75H1.87v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.9 10.66a5.4 5.4 0 0 1 0-3.44V4.9H1.87a9 9 0 0 0 0 8.09l2.03-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.33 0 2.53.46 3.47 1.35l2.59-2.59C13.5.98 11.45 0 9 0A9 9 0 0 0 1.87 4.9l2.03 2.32C4.62 5.07 6.63 3.58 9 3.58z"
      />
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
  const [notice, setNotice] = useState<string | null>(null);

  function switchMode(next: Mode) {
    if (busy || next === mode) return;
    setMode(next);
    setError(null);
    setNotice(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    if (!password) {
      setError("Enter your password.");
      return;
    }
    if (mode === "signup" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "signup") {
        await post<User>("/auth/signup", {
          name: name.trim() || "Agent",
          email: cleanEmail,
          password,
        });
      } else {
        await post<User>("/auth/login", {
          email: cleanEmail,
          password,
        });
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the backend running on port 8000?",
      );
      setBusy(false);
      return;
    }

    let me: User | null = null;
    try {
      me = await refreshUser();
    } catch {
      setError(
        `Signed in, but the session cookie was not saved. Open the app at ${window.location.origin} and try again.`,
      );
    }

    if (
      me &&
      !me.gmail_connected &&
      /@(gmail|googlemail)\.com$/i.test(cleanEmail)
    ) {
      try {
        await connectGmail();
        return;
      } catch {
        setError(
          "Signed in, but could not start the Gmail connection. Click Connect Gmail and try again.",
        );
      }
    }
    setBusy(false);
  }

  async function handleGoogle() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await connectGmail();
    } catch {
      setError("Could not start Google sign-in. Check the backend connection and try again.");
      setBusy(false);
    }
  }

  const inputClass =
    "w-full rounded-[8px] border border-[var(--border)] bg-white px-3 py-2.5 text-[13.5px] text-[var(--ink)] outline-none transition-colors focus:border-[var(--gold)] focus:ring-2 focus:ring-[var(--gold-weak)]";

  return (
    <div className="flex min-h-[100dvh] w-full items-center justify-center bg-[var(--paper)] px-4 py-10">
      <div className="w-full max-w-[380px]">
        <div className="mb-6 text-center">
          <div className="font-[family-name:var(--font-display)] text-[26px] font-semibold text-[var(--ink-strong)]">
            Smart <em className="text-[var(--gold)]">Inbox</em>
          </div>
          <p className="mt-1 text-[12.5px] text-[var(--muted)]">
            Turn 100 emails into 1 page.
          </p>
        </div>

        <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_10px_40px_rgba(38,43,32,0.08)]">
          <h1 className="text-[16px] font-semibold text-[var(--ink-strong)]">
            {mode === "signin" ? "Sign in" : "Create your account"}
          </h1>
          <p className="mt-1 text-[12px] text-[var(--muted)]">
            {mode === "signin"
              ? "Use the email and password for this workspace."
              : "Choose a password with at least 8 characters."}
          </p>

          <button
            type="button"
            onClick={() => void handleGoogle()}
            disabled={busy}
            className="mt-5 flex w-full cursor-pointer items-center justify-center gap-2.5 rounded-[8px] border border-[var(--border-strong)] bg-white px-3 py-2.5 text-[13.5px] font-medium text-[var(--ink)] transition-colors hover:bg-[var(--sunk)] disabled:cursor-wait disabled:opacity-60"
          >
            <GoogleMark />
            Continue with Google
          </button>

          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-[var(--border)]" />
            <span className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
              or email
            </span>
            <span className="h-px flex-1 bg-[var(--border)]" />
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-3">
            {mode === "signup" && (
              <label className="flex flex-col gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                  Name
                </span>
                <input
                  className={inputClass}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jordan Reeves"
                  autoComplete="name"
                  disabled={busy}
                />
              </label>
            )}

            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                Email
              </span>
              <input
                className={inputClass}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@agency.com"
                autoComplete="email"
                required
                disabled={busy}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                Password
              </span>
              <input
                className={inputClass}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                required
                disabled={busy}
              />
            </label>

            {error && (
              <p role="alert" className="rounded-[6px] bg-[var(--hot-weak)] px-3 py-2 text-[12px] leading-relaxed text-[var(--hot)]">
                {error}
              </p>
            )}
            {notice && (
              <p className="rounded-[6px] bg-[var(--ok-weak)] px-3 py-2 text-[12px] leading-relaxed text-[var(--ok)]">
                {notice}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mt-1 w-full cursor-pointer rounded-[8px] bg-[var(--gold)] px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[var(--gold-strong)] disabled:cursor-wait disabled:opacity-60"
            >
              {busy
                ? "Please wait…"
                : mode === "signin"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          <p className="mt-4 text-center text-[12px] text-[var(--muted)]">
            {mode === "signin" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}
              disabled={busy}
              className="cursor-pointer font-semibold text-[var(--gold-dark)] underline-offset-2 hover:underline disabled:opacity-60"
            >
              {mode === "signin" ? "Create one" : "Sign in"}
            </button>
          </p>
        </div>

        <p className="mt-4 text-center text-[11px] leading-relaxed text-[var(--muted)]">
          Connected Gmail before? Use <strong>Continue with Google</strong> — that
          account has no password.
        </p>
        <button
          type="button"
          onClick={() => {
            setNotice(
              "Password reset is not enabled yet. Use Continue with Google, or ask the workspace owner to set a password.",
            );
            setError(null);
          }}
          className="mx-auto mt-2 block cursor-pointer text-[11px] text-[var(--muted)] underline-offset-2 hover:underline"
        >
          Forgot password?
        </button>
      </div>
    </div>
  );
}
