"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Brand } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import {
  Alert,
  Badge,
  Button,
  Field,
  Input,
  Select,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

type Mode = "signin" | "register" | "forgot";

const TABS: { key: Mode; label: string }[] = [
  { key: "signin", label: "Sign in" },
  { key: "register", label: "Create account" },
];

/** Self-registration is candidate or examiner. Admin accounts are made by an admin. */
type RegisterRole = Exclude<UserRole, "admin">;

type FieldKey = "fullName" | "password" | "confirmPassword";
type FieldErrors = Partial<Record<FieldKey, string | undefined>>;

const PASSWORD_HINT = "At least 8 characters, with a letter and a digit.";
const MISMATCH_MESSAGE = "Passwords do not match.";
/** The same rule the API enforces, checked here so the round trip is not needed. */
const PASSWORD_RULE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

/** The API stores a first and last name; the form asks for one line. */
function splitName(fullName: string): { first_name: string; last_name: string } {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  return { first_name: parts[0] ?? "", last_name: parts.slice(1).join(" ") };
}

function validateRegistration(input: {
  fullName: string;
  password: string;
  confirmPassword: string;
}): FieldErrors {
  const errors: FieldErrors = {};

  if (!input.fullName.trim()) errors.fullName = "Enter your full name.";
  if (!PASSWORD_RULE.test(input.password)) errors.password = PASSWORD_HINT;

  if (!input.confirmPassword) {
    errors.confirmPassword = "Re-enter your password to confirm it.";
  } else if (input.password !== input.confirmPassword) {
    errors.confirmPassword = MISMATCH_MESSAGE;
  }

  return errors;
}

/** Password box with the show/hide control. */
function PasswordInput({
  visible,
  onToggle,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & {
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <span className="relative block">
      <Input {...rest} type={visible ? "text" : "password"} className="pr-16" />
      <button
        type="button"
        onClick={onToggle}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-1.5 my-auto h-7 rounded-[7px] px-2 text-[12px] font-medium text-ink-muted transition hover:bg-sunken hover:text-ink"
      >
        {visible ? "Hide" : "Show"}
      </button>
    </span>
  );
}

export default function LoginPage() {
  const { user, loginAccess, booting, signIn, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Every field starts empty. Nothing on this page is pre-filled.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<RegisterRole>("candidate");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  // Someone who is already signed in should never sit on the login screen.
  useEffect(() => {
    if (!booting && user) router.replace(homeFor(user, loginAccess));
  }, [user, loginAccess, booting, router]);

  if (booting) return <Splash />;

  // Mismatch is reported as soon as the second box has something in it, so the
  // candidate does not have to press the button to find out.
  const confirmError =
    fieldErrors.confirmPassword ??
    (confirmPassword && password !== confirmPassword ? MISMATCH_MESSAGE : undefined);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setNotice(null);
    setFieldErrors({});
    // Leaving a form empties it, so neither form ever opens holding stale input.
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setFullName("");
    setRole("candidate");
    setShowPassword(false);
    setShowConfirm(false);
  }

  function clearFieldError(key: FieldKey) {
    setFieldErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);

    try {
      if (mode === "signin") {
        const pair = await signIn(email.trim().toLowerCase(), password);

        if (pair.user.role === "candidate") {
          // An approved candidate is greeted before the dashboard; anyone still waiting
          // (or refused) goes straight to the page that explains why.
          if (pair.login_access === "approved") {
            router.replace("/candidate/welcome");
          } else if (pair.login_access === "rejected") {
            router.replace("/candidate/rejected");
          } else {
            router.replace("/candidate/pending");
          }
          return;
        }

        toast(`Welcome back, ${pair.user.first_name || pair.user.full_name}`, "mint");
        router.replace(homeFor(pair.user, pair.login_access));
        return;
      }

      if (mode === "register") {
        // Nothing reaches the API until the form itself is sound.
        const problems = validateRegistration({ fullName, password, confirmPassword });
        setFieldErrors(problems);
        if (Object.values(problems).some(Boolean)) return;

        const pair = await register({
          email: email.trim().toLowerCase(),
          password,
          ...splitName(fullName),
          role,
        });

        if (pair.user.role === "candidate") {
          // Registration itself is open: the account is active straight away. Approval
          // is asked for when they sign in, so send them to sign in.
          toast("Account created. Sign in to request access.", "mint");
          switchMode("signin");
          return;
        }

        toast("Account created — an administrator must approve it", "amber");
        router.replace(homeFor(pair.user, pair.login_access));
        return;
      }

      const response = await api.post<{ detail: string }>(
        "/auth/forgot-password",
        { email: email.trim().toLowerCase() },
        { auth: false },
      );
      setNotice(response.detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 bg-paper">
      {/* Subtle background pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(79,70,229,0.06),transparent)]" />

      <div className="relative grid w-full max-w-5xl overflow-hidden rounded-[20px] border border-line bg-surface shadow-[var(--shadow-lift)] lg:grid-cols-[1fr_1fr]">
        {/* ────────────────── Brand side ────────────────── */}
        <aside className="relative hidden flex-col justify-between overflow-hidden lg:flex" style={{ background: "#0f1117" }}>
          <div className="relative p-9 flex-1 flex flex-col justify-center">
            {/* Logo */}
            <Brand size={26} onDark className="mb-10" />

            <h1 className="text-[28px] font-bold leading-[1.2] tracking-tight text-white max-w-xs">
              Assessments that hold up to scrutiny.
            </h1>
            <p className="mt-3 max-w-sm text-[13.5px] leading-relaxed" style={{ color: "#a1a1b5" }}>
              AI-powered proctoring, randomized papers, automated grading — and a human examiner reviews every decision.
            </p>

            <div className="mt-8 space-y-3">
              {[
                { icon: "🎯", text: "Academic & Corporate exam modes" },
                { icon: "🤖", text: "AI question generation & grading" },
                { icon: "🔒", text: "Live proctoring with webcam monitoring" },
                { icon: "📊", text: "Deep performance analytics" },
              ].map((f) => (
                <div key={f.text} className="flex items-center gap-3">
                  <span className="text-[15px]">{f.icon}</span>
                  <span className="text-[13px]" style={{ color: "#a1a1b5" }}>{f.text}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Bottom gradient line */}
          <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-accent to-transparent opacity-40" />
        </aside>

        {/* ────────────────── Form side ────────────────── */}
        <section className="p-7 sm:p-9">
          <Brand className="mb-6 lg:hidden" />

          {mode !== "forgot" ? (
            <div className="mb-6 inline-flex rounded-[10px] border border-line bg-sunken p-1">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => switchMode(tab.key)}
                  className={cx(
                    "rounded-[7px] px-3.5 py-1.5 text-[13px] font-medium transition",
                    mode === tab.key
                      ? "bg-surface text-ink shadow-[var(--shadow-soft)]"
                      : "text-ink-muted hover:text-ink",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => switchMode("signin")}
              className="mb-6 text-[13px] font-medium text-accent hover:text-accent-ink"
            >
              ← Back to sign in
            </button>
          )}

          <h2 className="text-[20px] font-semibold tracking-tight text-ink">
            {mode === "signin"
              ? "Sign in to your account"
              : mode === "register"
                ? "Create your account"
                : "Reset your password"}
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            {mode === "signin"
              ? "Candidates, examiners and administrators use the same door."
              : mode === "register"
                ? "Candidate registration is open. Access to the platform is approved when you first sign in."
                : "We will issue a reset link for the address you registered with."}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === "register" && (
              <Field label="Full name" error={fieldErrors.fullName}>
                <Input
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    clearFieldError("fullName");
                  }}
                  placeholder="Enter your full name"
                  autoComplete="name"
                  required
                />
              </Field>
            )}

            <Field label="Email address">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email address"
                autoComplete="email"
                required
              />
            </Field>

            {mode !== "forgot" && (
              <Field
                label="Password"
                hint={mode === "register" ? PASSWORD_HINT : undefined}
                error={fieldErrors.password}
              >
                <PasswordInput
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    clearFieldError("password");
                  }}
                  placeholder="Enter your password"
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  visible={showPassword}
                  onToggle={() => setShowPassword((on) => !on)}
                  required
                  minLength={mode === "register" ? 8 : undefined}
                />
              </Field>
            )}

            {mode === "register" && (
              <Field label="Confirm password" error={confirmError}>
                <PasswordInput
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    clearFieldError("confirmPassword");
                  }}
                  placeholder="Re-enter your password"
                  autoComplete="new-password"
                  visible={showConfirm}
                  onToggle={() => setShowConfirm((on) => !on)}
                  required
                  minLength={8}
                />
              </Field>
            )}

            {mode === "register" && (
              <Field label="I am registering as">
                <Select
                  value={role}
                  onChange={(e) => setRole(e.target.value as RegisterRole)}
                >
                  <option value="candidate">Candidate</option>
                  <option value="examiner">Examiner</option>
                </Select>
              </Field>
            )}

            {mode === "signin" && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => switchMode("forgot")}
                  className="text-[12.5px] font-medium text-accent hover:text-accent-ink"
                >
                  Forgot password?
                </button>
              </div>
            )}

            {error && <Alert tone="rose">{error}</Alert>}
            {notice && (
              <Alert tone="mint" title="Check your inbox">
                {notice}
              </Alert>
            )}

            <Button type="submit" loading={busy} className="w-full">
              {mode === "signin"
                ? "Sign in"
                : mode === "register"
                  ? "Create account"
                  : "Send reset link"}
            </Button>
          </form>

          {mode === "forgot" && <ResetTokenForm onDone={() => switchMode("signin")} />}

          {mode === "signin" && <DemoAccounts onPick={(e, p) => { setEmail(e); setPassword(p); }} />}
        </section>
      </div>
    </main>
  );
}

/**
 * This deployment has no mail transport, so `forgot-password` returns the reset token
 * inline in development. This form completes the loop without an inbox.
 */
function ResetTokenForm({ onDone }: { onDone: () => void }) {
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { token: token.trim(), new_password: newPassword }, {
        auth: false,
      });
      toast("Password updated — sign in with your new password", "mint");
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-7 space-y-4 border-t border-line pt-6">
      <div className="flex items-center gap-2">
        <p className="text-[13px] font-semibold text-ink">Have a reset token?</p>
        <Badge tone="amber">no mail server</Badge>
      </div>
      <Field label="Reset token">
        <Input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Paste the token from the message above"
          required
        />
      </Field>
      <Field label="New password">
        <Input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="••••••••"
          minLength={8}
          required
        />
      </Field>
      {error && <Alert tone="rose">{error}</Alert>}
      <Button type="submit" variant="secondary" loading={busy} className="w-full">
        Set new password
      </Button>
    </form>
  );
}

const DEMO = [
  { role: "Administrator", email: "admin@exam.edu", password: "Admin@12345", tone: "accent" },
  { role: "Examiner (approved)", email: "examiner@exam.edu", password: "Passw0rd!", tone: "mint" },
  {
    role: "Examiner (pending)",
    email: "pending.examiner@exam.edu",
    password: "Passw0rd!",
    tone: "amber",
  },
  {
    role: "Candidate (login approved)",
    email: "candidate1@exam.edu",
    password: "Passw0rd!",
    tone: "neutral",
  },
  {
    role: "Candidate (login pending)",
    email: "candidate3@exam.edu",
    password: "Passw0rd!",
    tone: "amber",
  },
] as const;

function DemoAccounts({ onPick }: { onPick: (email: string, password: string) => void }) {
  return (
    <div className="mt-6 border-t border-line pt-5">
      <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
        Demo Accounts — Click to fill
      </p>
      <div className="grid gap-1.5">
        {DEMO.map((account) => (
          <button
            key={account.email}
            type="button"
            onClick={() => onPick(account.email, account.password)}
            className="flex items-center justify-between rounded-[9px] border border-line px-3 py-2 text-left transition hover:border-accent/40 hover:bg-accent-soft"
          >
            <span className="text-[12px] text-ink-soft font-mono">{account.email}</span>
            <Badge tone={account.tone}>{account.role}</Badge>
          </button>
        ))}
      </div>
    </div>
  );
}
