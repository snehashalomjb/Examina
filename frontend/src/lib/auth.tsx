"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api, tokens } from "@/lib/api";
import { isSupportedLocale, useLocale, type Locale } from "@/lib/locale";
import type { LoginAccess, LoginAccessStatus, TokenPair, User, UserRole } from "@/lib/types";

interface AuthState {
  user: User | null;
  /**
   * Candidates only. Their permission to *use* the platform, which is a separate axis
   * from whether the account exists — the account is created active at registration and
   * this is what an administrator or authorised examiner decides afterwards.
   */
  loginAccess: LoginAccessStatus | null;
  /** True until the very first `/auth/me` resolves - drives the splash screen. */
  booting: boolean;
  signIn: (email: string, password: string) => Promise<TokenPair>;
  register: (input: RegisterInput) => Promise<TokenPair>;
  signOut: () => void;
  refreshUser: () => Promise<void>;
  /**
   * What the language selector calls. Updates the UI instantly (no reload) and, when
   * signed in, persists the choice server-side so it follows the user across devices -
   * a no-op network call when signed out, since localStorage already carries it then.
   */
  changeLocale: (locale: Locale) => void;
}

export interface RegisterInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: Exclude<UserRole, "admin">;
}

const AuthContext = createContext<AuthState | null>(null);

/** Where a signed-in user belongs right now. */
export function homeFor(user: User, loginAccess?: LoginAccessStatus | null): string {
  if (user.role === "admin") return "/dashboard/admin";
  if (user.role === "examiner") return "/dashboard/examiner";

  // Candidates route on their login-approval state, not on the account.
  if (loginAccess === "rejected") return "/candidate/rejected";
  if (loginAccess && loginAccess !== "approved") return "/candidate/pending";
  return "/dashboard/candidate";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loginAccess, setLoginAccess] = useState<LoginAccessStatus | null>(null);
  const [booting, setBooting] = useState(true);
  const router = useRouter();
  const { locale, setLocale } = useLocale();

  const loadUser = useCallback(async () => {
    if (!tokens.access()) {
      setUser(null);
      setLoginAccess(null);
      return;
    }
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
      // The server is the source of truth once signed in - a locale picked before
      // login (or on another device) is reconciled here rather than left to drift.
      if (isSupportedLocale(me.preferred_locale) && me.preferred_locale !== locale) {
        setLocale(me.preferred_locale);
      }

      if (me.role === "candidate") {
        // Re-read on every boot so a revocation takes effect on the next page load
        // rather than lingering until the token expires.
        try {
          const access = await api.get<LoginAccess>("/auth/login-access");
          setLoginAccess(access.status);
        } catch {
          setLoginAccess("pending");
        }
      } else {
        setLoginAccess(null);
      }
    } catch {
      tokens.clear();
      setUser(null);
      setLoginAccess(null);
    }
  }, [locale, setLocale]);

  // The splash stays up a fixed 3s minimum regardless of how fast `/auth/me` actually
  // resolves - a sub-second flash reads as broken, not fast.
  const SPLASH_MIN_MS = 3000;

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    (async () => {
      await loadUser();
      const elapsed = Date.now() - started;
      const wait = Math.max(SPLASH_MIN_MS - elapsed, 0);
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
      if (!cancelled) setBooting(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadUser]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const pair = await api.post<TokenPair>("/auth/login", { email, password }, { auth: false });
      tokens.set(pair.access_token, pair.refresh_token);
      setUser(pair.user);
      setLoginAccess(pair.login_access);
      if (isSupportedLocale(pair.user.preferred_locale)) setLocale(pair.user.preferred_locale);
      return pair;
    },
    [setLocale],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const pair = await api.post<TokenPair>("/auth/register", input, { auth: false });
      tokens.set(pair.access_token, pair.refresh_token);
      setUser(pair.user);
      setLoginAccess(pair.login_access);
      if (isSupportedLocale(pair.user.preferred_locale)) setLocale(pair.user.preferred_locale);
      return pair;
    },
    [setLocale],
  );

  const signOut = useCallback(() => {
    tokens.clear();
    setUser(null);
    setLoginAccess(null);
    router.replace("/login");
  }, [router]);

  const changeLocale = useCallback(
    (next: Locale) => {
      setLocale(next);
      if (user) {
        // Fire-and-forget: a failed save just means the choice stays local-only until
        // the next successful one, which is not worth blocking the UI switch over.
        void api
          .patch("/auth/me", {
            first_name: user.first_name,
            last_name: user.last_name,
            preferred_locale: next,
          })
          .catch(() => {});
      }
    },
    [setLocale, user],
  );

  const value = useMemo(
    () => ({
      user,
      loginAccess,
      booting,
      signIn,
      register,
      signOut,
      refreshUser: loadUser,
      changeLocale,
    }),
    [user, loginAccess, booting, signIn, register, signOut, loadUser, changeLocale],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/**
 * Client-side route guard.
 *
 * The server enforces the real rules — every protected candidate route sits behind the
 * login-approval dependency in FastAPI. This only keeps the UI honest, so a pending
 * candidate lands on their status page instead of watching a dashboard fill with 403s.
 */
export function useRequireAuth(allowed?: UserRole[]) {
  const { user, loginAccess, booting } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (booting) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (allowed && !allowed.includes(user.role)) {
      router.replace(homeFor(user, loginAccess));
      return;
    }
    if (user.role === "candidate" && loginAccess && loginAccess !== "approved") {
      router.replace(loginAccess === "rejected" ? "/candidate/rejected" : "/candidate/pending");
    }
  }, [user, loginAccess, booting, allowed, router]);

  return { user, loginAccess, booting };
}
