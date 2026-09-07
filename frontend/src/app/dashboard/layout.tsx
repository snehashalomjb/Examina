"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Brand } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import { Badge, Button, cx } from "@/components/ui";
import {
  IconBank,
  IconDashboard,
  IconExam,
  IconGrading,
  IconPerformance,
  IconProfile,
  IconResults,
  IconSettings,
  IconShield,
  IconSignOut,
  IconUsers,
} from "@/components/icons";
import { useAuth, useRequireAuth } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

type IconComponent = (props: { size?: number; className?: string }) => React.JSX.Element;

interface NavItem {
  href: string;
  label: string;
  roles: UserRole[];
  icon: IconComponent;
  badge?: string;
  needsApproval?: boolean;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [
      { href: "/dashboard/admin",              label: "Dashboard",     roles: ["admin"],               icon: IconDashboard },
      { href: "/dashboard/examiner",           label: "Dashboard",     roles: ["examiner"],            icon: IconDashboard },
      { href: "/dashboard/candidate",          label: "Dashboard",     roles: ["candidate"],           icon: IconDashboard },
      { href: "/dashboard/candidate/exams",    label: "My Exams",      roles: ["candidate"],           icon: IconExam },
      { href: "/dashboard/results",            label: "Results",       roles: ["candidate"],           icon: IconResults },
      { href: "/dashboard/candidate/performance", label: "Performance", roles: ["candidate"],          icon: IconPerformance },
    ],
  },
  {
    section: "Assessment",
    items: [
      { href: "/dashboard/exams",              label: "Exams",         roles: ["admin", "examiner"],   icon: IconExam,     needsApproval: true },
      { href: "/dashboard/exams/create",       label: "Create Exam",   roles: ["admin", "examiner"],   icon: PlusCircleIcon, needsApproval: true },
      { href: "/dashboard/questions",          label: "Question Bank", roles: ["admin", "examiner"],   icon: IconBank,     needsApproval: true },
      { href: "/dashboard/questions/ai-generate", label: "AI Tools",   roles: ["admin", "examiner"],  icon: SparkleIcon,  needsApproval: true, badge: "AI" },
      { href: "/dashboard/grading",            label: "Grading",       roles: ["admin", "examiner"],   icon: IconGrading,  needsApproval: true },
      { href: "/dashboard/proctoring",         label: "Proctoring",    roles: ["admin", "examiner"],   icon: IconShield,   needsApproval: true },
    ],
  },
  {
    section: "People",
    items: [
      { href: "/dashboard/candidates",         label: "Candidates",    roles: ["admin", "examiner"],   icon: IconUsers,    needsApproval: true },
      { href: "/dashboard/login-requests",     label: "Login Requests", roles: ["admin", "examiner"],  icon: BellIcon,     needsApproval: true },
      { href: "/dashboard/admin/users",        label: "Access Control", roles: ["admin"],              icon: IconShield },
    ],
  },
  {
    section: "Account",
    items: [
      { href: "/dashboard/profile",            label: "Profile",       roles: ["candidate", "examiner", "admin"], icon: IconProfile },
      { href: "/dashboard/settings",           label: "Settings",      roles: ["candidate", "examiner", "admin"], icon: IconSettings },
    ],
  },
];

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "Administrator",
  examiner: "Examiner",
  candidate: "Candidate",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, booting } = useRequireAuth();
  const { signOut } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close drawer on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (mobileOpen && drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        setMobileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [mobileOpen]);

  // Close drawer on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Prevent body scroll when mobile drawer open
  useEffect(() => {
    if (mobileOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  if (booting || !user) return <Splash />;

  const approved = user.access_status === "approved";
  const sections = NAV.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.roles.includes(user.role)),
  })).filter((section) => section.items.length > 0);

  const navContent = (
    <nav className="flex flex-col gap-5 flex-1 overflow-y-auto px-3 py-4 dark-scroll">
      {sections.map((section) => (
        <div key={section.section}>
          <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: "var(--color-sidebar-label)" }}>
            {section.section}
          </p>
          <div className="flex flex-col gap-0.5">
            {section.items.map((item) => {
              const Icon = item.icon;
              const locked = Boolean(item.needsApproval) && user.role !== "admin" && !approved;
              const isSectionRoot = item.href === "/dashboard/admin" || item.href === "/dashboard/candidate";
              const active = isSectionRoot
                ? pathname === item.href
                : pathname === item.href || pathname.startsWith(`${item.href}/`);

              if (locked) {
                return (
                  <span
                    key={item.href}
                    title="Awaiting administrator approval"
                    className="flex cursor-not-allowed items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] opacity-40"
                    style={{ color: "var(--color-sidebar-text)" }}
                  >
                    <Icon size={15} />
                    <span className="flex-1">{item.label}</span>
                    <LockIcon />
                  </span>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cx(
                    "group flex items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] font-medium transition-all",
                    active
                      ? "text-white"
                      : "hover:text-white",
                  )}
                  style={active
                    ? { background: "var(--color-sidebar-active)", color: "white" }
                    : { color: "var(--color-sidebar-text)" }
                  }
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--color-sidebar-hover)"; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = ""; }}
                >
                  <Icon
                    size={15}
                    className={cx(active ? "text-white" : "text-[var(--color-sidebar-text)] group-hover:text-white")}
                  />
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className="rounded-full bg-accent px-1.5 py-0.5 text-[9px] font-bold text-white">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const sidebarBottom = (
    <div className="border-t px-4 py-3 shrink-0" style={{ borderColor: "var(--color-sidebar-border)" }}>
      <div className="flex items-center gap-2.5 rounded-[10px] px-2 py-2.5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/20 text-[12px] font-bold text-accent">
          {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-white">{user.full_name}</p>
          <p className="truncate text-[11px]" style={{ color: "var(--color-sidebar-text)" }}>
            {ROLE_LABEL[user.role]}
          </p>
        </div>
      </div>
      <button
        onClick={signOut}
        className="mt-1 flex w-full items-center gap-2.5 rounded-[8px] px-3 py-2 text-[13px] font-medium transition-all"
        style={{ color: "var(--color-sidebar-text)" }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-sidebar-hover)"; e.currentTarget.style.color = "white"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = ""; e.currentTarget.style.color = "var(--color-sidebar-text)"; }}
      >
        <IconSignOut size={14} />
        Sign out
      </button>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* ───────── Desktop sidebar ───────── */}
      <aside
        className="relative hidden w-[240px] shrink-0 flex-col lg:flex"
        style={{ background: "var(--color-sidebar)", borderRight: "1px solid var(--color-sidebar-border)" }}
      >
        {/* Logo */}
        <div className="flex h-16 shrink-0 items-center px-5" style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
          <Brand onDark />
        </div>

        {navContent}
        {sidebarBottom}
      </aside>

      {/* ───────── Mobile slide-over drawer ───────── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/60 backdrop-blur-[2px] animate-fade" />
          <div
            ref={drawerRef}
            className="absolute inset-y-0 left-0 flex w-[260px] flex-col animate-slide-right"
            style={{ background: "var(--color-sidebar)" }}
          >
            <div className="flex h-16 shrink-0 items-center gap-2.5 px-5" style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
              <Brand onDark />
              <button
                onClick={() => setMobileOpen(false)}
                className="ml-auto rounded-[6px] p-1.5 hover:bg-white/10"
                style={{ color: "var(--color-sidebar-text)" }}
                aria-label="Close navigation"
              >
                <CloseIcon />
              </button>
            </div>
            {navContent}
            {sidebarBottom}
          </div>
        </div>
      )}

      {/* ───────── Main content ───────── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top header */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-line bg-paper/90 px-4 backdrop-blur-md lg:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-line text-ink-soft hover:bg-sunken transition lg:hidden"
              aria-label="Open navigation"
            >
              <HamburgerIcon />
            </button>
            {/* Breadcrumb / greeting */}
            <div className="hidden sm:block">
              <p className="text-[13.5px] font-semibold text-ink">
                {greeting()}, {user.full_name.split(" ")[0]} 👋
              </p>
              <p className="text-[11.5px] text-ink-muted">{ROLE_LABEL[user.role]} workspace</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Access status badge */}
            {user.role !== "admin" && !approved && (
              <Badge tone={user.access_status === "pending" ? "amber" : "rose"} size="xs">
                {user.access_status === "pending" ? "Pending approval" : "Access revoked"}
              </Badge>
            )}
            {user.role !== "admin" && approved && (
              <Badge tone="green" size="xs">Active</Badge>
            )}
            {/* User avatar */}
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-[12px] font-bold text-accent">
              {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
            </div>
            {/* Mobile sign out */}
            <Button variant="ghost" size="sm" className="lg:hidden text-[12px]" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="min-w-0 flex-1 px-4 py-6 lg:px-7 lg:py-7">
          <div className="mx-auto w-full max-w-[1200px] animate-rise">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/* ─── Inline icon components ────────────────────────────────────── */
function SparkleIcon({ size = 15, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z" />
    </svg>
  );
}

function BellIcon({ size = 15, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function HamburgerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path d="M1 3h12M1 7h12M1 11h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3.5" y="7" width="9" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5.75 7V5.25a2.25 2.25 0 0 1 4.5 0V7" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function PlusCircleIcon({ size = 15, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}


