"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ProjectDashboard } from "@/components/ProjectDashboard";
import {
  AuthApiError,
  getCurrentUser,
  login,
  logout,
  registerAccount,
  type AuthUser,
} from "@/lib/authApi";

type View = "login" | "register";

const fieldClass =
  "w-full rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]";

const AuthField = ({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children?: ReactNode;
}) => (
  <div>
    <label
      htmlFor={id}
      className="mb-2 block text-sm font-semibold text-[var(--navy-dark)]"
    >
      {label}
    </label>
    {children}
  </div>
);

export const AuthGate = () => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [view, setView] = useState<View>("login");
  const [loadingSession, setLoadingSession] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((authError: unknown) => {
        if (active && !(authError instanceof AuthApiError && authError.status === 401)) {
          setError(
            authError instanceof Error
              ? authError.message
              : "Unable to check your sign-in status."
          );
        }
      })
      .finally(() => {
        if (active) setLoadingSession(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const run = async (
    event: FormEvent<HTMLFormElement>,
    action: () => Promise<void>
  ) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : "The request could not be completed."
      );
    } finally {
      setBusy(false);
    }
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    await run(event, async () => {
      const form = new FormData(event.currentTarget);
      const result = await login(
        String(form.get("identifier")),
        String(form.get("password"))
      );
      setUser(result.user);
    });
  };

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    await run(event, async () => {
      const form = new FormData(event.currentTarget);
      const password = String(form.get("password"));
      if (password !== String(form.get("confirm_password"))) {
        throw new Error("Passwords do not match.");
      }
      const username = String(form.get("username")).trim();
      await registerAccount({ username, password });
      const result = await login(username, password);
      setUser(result.user);
    });
  };

  const handleLogout = async () => {
    setBusy(true);
    setError("");
    try {
      await logout();
      setUser(null);
      setView("login");
      setNotice("You have been signed out.");
    } catch (logoutError) {
      setError(
        logoutError instanceof Error ? logoutError.message : "Unable to sign out."
      );
    } finally {
      setBusy(false);
    }
  };

  if (loadingSession) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-[var(--gray-text)]">
        Checking your session...
      </main>
    );
  }

  if (user) {
    return <ProjectDashboard onLogout={handleLogout} currentUser={user} />;
  }

  const titles: Record<View, string> = {
    login: "Sign in to Kanban Studio",
    register: "Create your account",
  };
  const descriptions: Record<View, string> = {
    login: "Sign in with the username and password you created.",
    register:
      "Use 12+ characters with variety, or a passphrase of at least 20 characters.",
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.2)_0%,_rgba(32,157,215,0.04)_55%,_transparent_70%)]" />
      <section className="relative w-full max-w-md rounded-[32px] border border-[var(--stroke)] bg-white/90 p-8 shadow-[var(--shadow)] backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
          Single Board Kanban
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]">
          {titles[view]}
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          {descriptions[view]}
        </p>

        {error && (
          <p role="alert" className="mt-5 text-sm font-medium text-red-700">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="mt-5 text-sm font-medium text-[var(--primary-blue)]">
            {notice}
          </p>
        )}

        {view === "login" && (
          <form onSubmit={handleLogin} className="mt-8 space-y-5">
            <AuthField id="identifier" label="Username">
              <input
                id="identifier"
                name="identifier"
                autoComplete="username"
                required
                className={fieldClass}
              />
            </AuthField>
            <AuthField id="password" label="Password">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                className={fieldClass}
              />
            </AuthField>
            <label className="flex items-center gap-2 text-sm text-[var(--gray-text)]">
              <input
                type="checkbox"
                checked={showPassword}
                onChange={(event) => setShowPassword(event.target.checked)}
              />
              Show password
            </label>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
            >
              {busy ? "Signing in..." : "Sign in"}
            </button>
            <div className="flex justify-center text-sm">
              <button type="button" className="text-[var(--primary-blue)]" onClick={() => { setError(""); setNotice(""); setView("register"); }}>
                Create account
              </button>
            </div>
            <p className="text-center text-xs text-[var(--gray-text)]">
              Forgot your password? Create a new account. This demo does not use email recovery.
            </p>
          </form>
        )}

        {view === "register" && (
          <form onSubmit={handleRegister} className="mt-8 space-y-4">
            <AuthField id="username" label="Username">
              <input id="username" name="username" autoComplete="username" required minLength={3} maxLength={30} pattern="[A-Za-z0-9_]+" className={fieldClass} />
            </AuthField>
            <AuthField id="register-password" label="Password">
              <input id="register-password" name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} className={fieldClass} />
            </AuthField>
            <AuthField id="confirm_password" label="Confirm password">
              <input id="confirm_password" name="confirm_password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} className={fieldClass} />
            </AuthField>
            <label className="flex items-center gap-2 text-sm text-[var(--gray-text)]">
              <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
              Show password
            </label>
            <button type="submit" disabled={busy} className="w-full rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">
              {busy ? "Creating account..." : "Create account"}
            </button>
            <p className="text-center text-sm text-[var(--gray-text)]">
              Already registered?{" "}
              <button type="button" className="text-[var(--primary-blue)]" onClick={() => { setError(""); setNotice(""); setView("login"); }}>
                Sign in
              </button>
            </p>
          </form>
        )}

      </section>
    </main>
  );
};
