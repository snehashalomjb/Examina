"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api, tokens } from "@/lib/api";
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

  const loadUser = useCallback(async () => {
    if (!tokens.access()) {
      setUser(null);
      setLoginAccess(null);
      return;
    }
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);

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
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadUser();
      if (!cancelled) setBooting(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadUser]);

  const signIn = useCallback(async (email: string, password: string) => {
    const pair = await api.post<TokenPair>("/auth/login", { email, password }, { auth: false });
    tokens.set(pair.access_token, pair.refresh_token);
    setUser(pair.user);
    setLoginAccess(pair.login_access);
    return pair;
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    const pair = await api.post<TokenPair>("/auth/register", input, { auth: false });
    tokens.set(pair.access_token, pair.refresh_token);
    setUser(pair.user);
    setLoginAccess(pair.login_access);
    return pair;
  }, []);

  const signOut = useCallback(() => {
    tokens.clear();
    setUser(null);
    setLoginAccess(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loginAccess, booting, signIn, register, signOut, refreshUser: loadUser }),
    [user, loginAccess, booting, signIn, register, signOut, loadUser],
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
