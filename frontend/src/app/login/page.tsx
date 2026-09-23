"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { LanguageSelector } from "@/components/LanguageSelector";
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

/** Self-registration is candidate or examiner. Admin accounts are made by an admin. */
type RegisterRole = Exclude<UserRole, "admin">;

type FieldKey = "fullName" | "password" | "confirmPassword";
type FieldErrors = Partial<Record<FieldKey, string | undefined>>;

/** The same rule the API enforces, checked here so the round trip is not needed. */
const PASSWORD_RULE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

/** The API stores a first and last name; the form asks for one line. */
function splitName(fullName: string): { first_name: string; last_name: string } {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  return { first_name: parts[0] ?? "", last_name: parts.slice(1).join(" ") };
}

function validateRegistration(
  input: { fullName: string; password: string; confirmPassword: string },
  tv: (key: string) => string,
): FieldErrors {
  const errors: FieldErrors = {};

  if (!input.fullName.trim()) errors.fullName = tv("required_field");
  if (!PASSWORD_RULE.test(input.password)) errors.password = tv("password_too_short");

  if (!input.confirmPassword) {
    errors.confirmPassword = tv("required_field");
  } else if (input.password !== input.confirmPassword) {
    errors.confirmPassword = tv("passwords_mismatch");
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
        className="absolute inset-y-0 right-1.5 my-auto h-7 rounded-[7px] px-2.5 text-[12px] font-semibold text-ink-muted transition hover:bg-sunken hover:text-ink"
      >
        {visible ? "Hide" : "Show"}
      </button>
    </span>
  );
}

export default function LoginPage() {
  const { user, loginAccess, booting, signIn, register } = useAuth();
  const router = useRouter();
  const t = useTranslations("auth");
  const tv = useTranslations("validation");
  const tc = useTranslations("common");

  const TABS: { key: Mode; label: string }[] = [
    { key: "signin", label: t("login_button") },
    { key: "register", label: t("register_button") },
  ];

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

  // Mismatch is reported as soon as the second box has something in it
  const confirmError =
    fieldErrors.confirmPassword ??
    (confirmPassword && password !== confirmPassword ? tv("passwords_mismatch") : undefined);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setNotice(null);
    setFieldErrors({});
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
        const problems = validateRegistration({ fullName, password, confirmPassword }, tv);
        setFieldErrors(problems);
        if (Object.values(problems).some(Boolean)) return;

        const pair = await register({
          email: email.trim().toLowerCase(),
          password,
          ...splitName(fullName),
          role,
        });

        if (pair.user.role === "candidate") {
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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10"
      style={{ background: "#070a14" }}>

      {/* ── Aurora background orbs ── */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="aurora-orb animate-glow-pulse" style={{
          width: 700, height: 700,
          background: "radial-gradient(circle, rgba(79,70,229,0.18) 0%, transparent 65%)",
          top: "-25%", left: "-15%",
        }} />
        <div className="aurora-orb" style={{
          width: 600, height: 600,
          background: "radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 65%)",
          bottom: "-20%", right: "-10%",
          animationDelay: "1.5s",
        }} />
        <div className="aurora-orb animate-glow-pulse" style={{
          width: 400, height: 400,
          background: "radial-gradient(circle, rgba(6,182,212,0.09) 0%, transparent 70%)",
          top: "40%", right: "20%",
          animationDelay: "0.8s",
        }} />
        {/* Subtle grid */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: "linear-gradient(rgba(99,102,241,1) 1px, transparent 1px), linear-gradient(to right, rgba(99,102,241,1) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }} />
      </div>

      {/* ── Main card ── */}
      <div className="relative w-full max-w-5xl overflow-hidden rounded-[24px] animate-rise"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 0 0 1px rgba(99,102,241,0.1), 0 32px 80px -16px rgba(0,0,0,0.7), 0 8px 24px -8px rgba(79,70,229,0.2)",
        }}>
        <div className="lg:grid lg:grid-cols-[1fr_1fr]">

          {/* ─────────── Brand side ─────────── */}
          <aside className="relative hidden flex-col justify-between overflow-hidden lg:flex"
            style={{ background: "linear-gradient(160deg, #0a0d1e 0%, #0f1535 50%, #0d0a1e 100%)" }}>

            {/* Geometric accent mesh */}
            <div className="absolute inset-0 pointer-events-none">
              <div style={{
                position: "absolute", top: 0, right: 0, width: "60%", height: "100%",
                background: "radial-gradient(ellipse at 100% 0%, rgba(99,102,241,0.12) 0%, transparent 60%)",
              }} />
              <div style={{
                position: "absolute", bottom: 0, left: 0, width: "50%", height: "60%",
                background: "radial-gradient(ellipse at 0% 100%, rgba(139,92,246,0.08) 0%, transparent 60%)",
              }} />
              {/* Decorative grid lines */}
              <div className="absolute inset-0 opacity-[0.04]"
                style={{
                  backgroundImage: "linear-gradient(rgba(139,92,246,1) 1px, transparent 1px), linear-gradient(to right, rgba(139,92,246,1) 1px, transparent 1px)",
                  backgroundSize: "40px 40px",
                }} />
            </div>

            <div className="relative p-10 flex-1 flex flex-col justify-center">
              {/* Logo */}
              <div className="mb-10 animate-rise" style={{ animationDelay: "0.05s" }}>
                <Brand size={26} onDark />
              </div>

              {/* Headline */}
              <div className="animate-rise" style={{ animationDelay: "0.1s" }}>
                <h1 className="text-[30px] font-bold leading-[1.2] tracking-tight text-white max-w-xs">
                  Assessments that hold up to{" "}
                  <span style={{
                    background: "linear-gradient(135deg, #818cf8, #a5b4fc)",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}>
                    scrutiny.
                  </span>
                </h1>
                <p className="mt-4 max-w-sm text-[13.5px] leading-relaxed" style={{ color: "#8b8ba7" }}>
                  AI-powered proctoring, randomized papers, automated grading — and a human examiner reviews every decision.
                </p>
              </div>

              {/* Feature list */}
              <div className="mt-9 space-y-3.5 animate-rise" style={{ animationDelay: "0.15s" }}>
                {[
                  { icon: "🎯", text: "Academic & Corporate exam modes", color: "#818cf8" },
                  { icon: "🤖", text: "AI question generation & grading", color: "#a5b4fc" },
                  { icon: "🔒", text: "Live proctoring with webcam monitoring", color: "#818cf8" },
                  { icon: "📊", text: "Deep performance analytics", color: "#a5b4fc" },
                ].map((f, i) => (
                  <div key={f.text} className="flex items-center gap-3.5 animate-rise"
                    style={{ animationDelay: `${0.2 + i * 0.05}s` }}>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px]"
                      style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.2)" }}>
                      <span className="text-[14px]">{f.icon}</span>
                    </div>
                    <span className="text-[13px] font-medium" style={{ color: "#a1a1b5" }}>{f.text}</span>
                  </div>
                ))}
              </div>

              {/* Bottom stat strip */}
              <div className="mt-10 grid grid-cols-3 gap-4 animate-rise" style={{ animationDelay: "0.35s" }}>
                {[
                  { value: "10K+", label: "Exams taken" },
                  { value: "99.8%", label: "Uptime" },
                  { value: "4.9★", label: "Avg. rating" },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-[12px] px-3 py-3 text-center"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.07)",
                    }}>
                    <p className="text-[16px] font-bold text-white">{stat.value}</p>
                    <p className="mt-0.5 text-[10px] font-medium" style={{ color: "#6b6b8a" }}>{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom gradient line */}
            <div className="h-[2px] w-full bg-gradient-to-r from-transparent via-indigo-500 to-transparent opacity-40" />
          </aside>

          {/* ─────────── Form side ─────────── */}
          <section className="relative p-7 sm:p-9" style={{ background: "rgba(255,255,255,0.97)" }}>
            <div className="mb-4 flex items-center justify-between">
              {/* Mobile brand */}
              <Brand className="lg:hidden" />
              <LanguageSelector className="ml-auto" />
            </div>

            {/* Mode tabs */}
            {mode !== "forgot" ? (
              <div className="mb-7 inline-flex rounded-[12px] border border-line bg-sunken p-1">
                {TABS.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => switchMode(tab.key)}
                    className={cx(
                      "rounded-[9px] px-4 py-1.5 text-[13px] font-semibold transition-all duration-200",
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
                className="mb-7 flex items-center gap-1.5 text-[13px] font-semibold text-accent hover:text-accent-ink transition-colors"
              >
                <span>←</span> {t("sign_in_here")}
              </button>
            )}

            {/* Heading */}
            <div className="mb-6">
              <h2 className="text-[22px] font-bold tracking-tight text-ink">
                {mode === "signin"
                  ? t("login_title")
                  : mode === "register"
                    ? t("register_title")
                    : t("reset_password_title")}
              </h2>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
                {mode === "signin"
                  ? t("login_subtitle")
                  : mode === "register"
                    ? t("register_subtitle")
                    : t("reset_password_title")}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "register" && (
                <Field label={tc("name")} error={fieldErrors.fullName}>
                  <Input
                    value={fullName}
                    onChange={(e) => {
                      setFullName(e.target.value);
                      clearFieldError("fullName");
                    }}
                    placeholder={tc("name")}
                    autoComplete="name"
                    required
                  />
                </Field>
              )}

              <Field label={t("email")}>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t("email")}
                  autoComplete="email"
                  required
                />
              </Field>

              {mode !== "forgot" && (
                <Field
                  label={t("password")}
                  hint={mode === "register" ? t("password_requirements") : undefined}
                  error={fieldErrors.password}
                >
                  <PasswordInput
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      clearFieldError("password");
                    }}
                    placeholder={t("password")}
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    visible={showPassword}
                    onToggle={() => setShowPassword((on) => !on)}
                    required
                    minLength={mode === "register" ? 8 : undefined}
                  />
                </Field>
              )}

              {mode === "register" && (
                <Field label={t("confirm_password")} error={confirmError}>
                  <PasswordInput
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      clearFieldError("confirmPassword");
                    }}
                    placeholder={t("confirm_password")}
                    autoComplete="new-password"
                    visible={showConfirm}
                    onToggle={() => setShowConfirm((on) => !on)}
                    required
                    minLength={8}
                  />
                </Field>
              )}

              {mode === "register" && (
                <Field label={t("role")}>
                  <Select
                    value={role}
                    onChange={(e) => setRole(e.target.value as RegisterRole)}
                  >
                    <option value="candidate">{t("role_candidate")}</option>
                    <option value="examiner">{t("role_examiner")}</option>
                  </Select>
                </Field>
              )}

              {mode === "signin" && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => switchMode("forgot")}
                    className="text-[12.5px] font-semibold text-accent hover:text-accent-ink transition-colors"
                  >
                    {t("forgot_password")}
                  </button>
                </div>
              )}

              {error && <Alert tone="rose">{error}</Alert>}
              {notice && (
                <Alert tone="mint" title="Check your inbox">
                  {notice}
                </Alert>
              )}

              <Button type="submit" loading={busy} className="w-full" size="lg">
                {mode === "signin"
                  ? t("login_button")
                  : mode === "register"
                    ? t("register_button")
                    : t("reset_password_button")}
              </Button>
            </form>

            {mode === "forgot" && <ResetTokenForm onDone={() => switchMode("signin")} />}

            {mode === "signin" && <DemoAccounts onPick={(e, p) => { setEmail(e); setPassword(p); }} />}
          </section>
        </div>
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
      <p className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.1em] text-ink-muted">
        Demo Accounts — Click to fill
      </p>
      <div className="grid gap-1.5">
        {DEMO.map((account) => (
          <button
            key={account.email}
            type="button"
            onClick={() => onPick(account.email, account.password)}
            className="group flex items-center justify-between rounded-[10px] border border-line px-3.5 py-2.5 text-left transition-all duration-200 hover:border-accent/30 hover:bg-accent-soft hover:shadow-sm"
          >
            <span className="text-[12px] text-ink-muted font-mono group-hover:text-ink-soft transition-colors">{account.email}</span>
            <Badge tone={account.tone}>{account.role}</Badge>
          </button>
        ))}
      </div>
    </div>
  );
}
