"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Avatar } from "@/components/Avatar";
import { LanguageSelector } from "@/components/LanguageSelector";
import { Brand } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import { Badge, Button, cx } from "@/components/ui";
import {
  IconBank,
  IconDashboard,
  IconExam,
  IconGrading,
  IconMonitor,
  IconPerformance,
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
      { href: "/dashboard/live",               label: "Live Console",  roles: ["admin", "examiner"],   icon: IconDashboard, needsApproval: true, badge: "LIVE" },
    ],
  },
  {
    section: "People",
    items: [
      { href: "/dashboard/candidates",         label: "Candidates",    roles: ["admin", "examiner"],   icon: IconUsers,    needsApproval: true },
      { href: "/dashboard/admin/users?role=examiner", label: "Examiners", roles: ["admin"],            icon: IconUsers },
      { href: "/dashboard/login-requests",     label: "Login Requests", roles: ["admin", "examiner"],  icon: BellIcon,     needsApproval: true },
      { href: "/dashboard/admin/users",        label: "User Management", roles: ["admin"],             icon: IconShield },
    ],
  },
  {
    // Admin-only: a platform-wide view over data that already exists (results,
    // proctoring, exams) plus what can honestly be exported today.
    section: "Reports",
    items: [
      { href: "/dashboard/admin/reports?tab=exams",       label: "Exam Reports",        roles: ["admin"], icon: IconExam },
      { href: "/dashboard/admin/reports?tab=candidates",  label: "Candidate Reports",   roles: ["admin"], icon: IconUsers },
      { href: "/dashboard/admin/reports?tab=proctoring",  label: "Proctoring Reports",  roles: ["admin"], icon: IconShield },
      { href: "/dashboard/admin/reports?tab=performance", label: "Performance Reports", roles: ["admin"], icon: IconPerformance },
      { href: "/dashboard/admin/reports?tab=export",      label: "Export Reports",      roles: ["admin"], icon: IconResults },
    ],
  },
  {
    section: "System",
    items: [
      { href: "/dashboard/admin/audit",          label: "Audit Logs",    roles: ["admin"], icon: IconResults },
      { href: "/dashboard/admin/system-health",  label: "System Health", roles: ["admin"], icon: IconMonitor },
    ],
  },
  {
    // Profile is no longer its own nav entry - the logo opens it instead, everywhere.
    section: "Account",
    items: [
      { href: "/dashboard/settings",           label: "Settings",      roles: ["candidate", "examiner", "admin"], icon: IconSettings },
    ],
  },
];

const ROLE_LABEL_KEY: Record<UserRole, string> = {
  admin: "role_admin",
  examiner: "role_examiner",
  candidate: "role_candidate",
};

// Only the items with a stable (query-string-free) href are translated in this pass -
// the rest (e.g. "Examiners", "Create Exam", per-tab report links) keep their English
// label for now, translatable later by adding a row here plus the matching message key.
const NAV_LABEL_KEY: Record<string, { ns: "dashboard" | "common"; key: string }> = {
  "/dashboard/admin": { ns: "common", key: "dashboard" },
  "/dashboard/examiner": { ns: "common", key: "dashboard" },
  "/dashboard/candidate": { ns: "common", key: "dashboard" },
  "/dashboard/candidate/exams": { ns: "dashboard", key: "nav_my_exams" },
  "/dashboard/results": { ns: "dashboard", key: "nav_results" },
  "/dashboard/candidate/performance": { ns: "dashboard", key: "nav_performance" },
  "/dashboard/exams": { ns: "dashboard", key: "nav_exams" },
  "/dashboard/questions": { ns: "dashboard", key: "nav_questions" },
  "/dashboard/grading": { ns: "dashboard", key: "nav_grading" },
  "/dashboard/proctoring": { ns: "dashboard", key: "nav_proctoring" },
  "/dashboard/candidates": { ns: "dashboard", key: "nav_candidates" },
  "/dashboard/admin/users": { ns: "dashboard", key: "nav_users" },
  "/dashboard/login-requests": { ns: "dashboard", key: "nav_login_requests" },
  "/dashboard/admin/audit": { ns: "dashboard", key: "nav_audit" },
  "/dashboard/admin/system-health": { ns: "dashboard", key: "nav_system_health" },
  "/dashboard/settings": { ns: "common", key: "settings" },
};

const SECTION_LABEL_KEY: Record<string, string> = {
  Overview: "section_overview",
  Assessment: "section_assessment",
  People: "section_people",
  Reports: "section_reports",
  System: "section_system",
};

const ROLE_GRADIENT: Record<UserRole, string> = {
  admin: "from-rose to-orange-400",
  examiner: "from-accent to-indigo-400",
  candidate: "from-green to-teal-400",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, booting } = useRequireAuth();
  const { signOut } = useAuth();
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  const navLabel = (item: NavItem) => {
    const mapped = NAV_LABEL_KEY[item.href];
    if (!mapped) return item.label;
    return mapped.ns === "common" ? tc(mapped.key) : t(mapped.key);
  };
  const sectionLabel = (section: string) => {
    const key = SECTION_LABEL_KEY[section];
    return key ? t(key) : section;
  };
  const roleLabel = (role: UserRole) => tc(ROLE_LABEL_KEY[role]);
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Which examiner header dropdown is open, if any. Only one at a time.
  const [openMenu, setOpenMenu] = useState<
    "assessment" | "monitoring" | "people" | "reports" | "system" | "profile" | null
  >(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // Close drawer on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (mobileOpen && drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        setMobileOpen(false);
      }
      if (openMenu && headerRef.current && !headerRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [mobileOpen, openMenu]);

  // Escape closes whichever examiner header dropdown is open.
  useEffect(() => {
    if (!openMenu) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenMenu(null);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [openMenu]);

  // Close drawer/dropdowns on route change
  useEffect(() => { setMobileOpen(false); setOpenMenu(null); }, [pathname]);

  // Prevent body scroll when mobile drawer open
  useEffect(() => {
    if (mobileOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  if (booting || !user) return <Splash />;

  const approved = user.access_status === "approved";
  const isCandidate = user.role === "candidate";
  const isExaminer = user.role === "examiner";
  const isAdmin = user.role === "admin";
  const sections = NAV.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.roles.includes(user.role)),
  })).filter((section) => section.items.length > 0);
  // Settings lives inside the Profile page for candidates, not as its own top-nav link.
  const candidateNavItems = sections
    .flatMap((section) => section.items)
    .filter((item) => item.href !== "/dashboard/settings");

  const assessmentItems = sections.find((s) => s.section === "Assessment")?.items ?? [];
  const peopleItems = sections.find((s) => s.section === "People")?.items ?? [];
  const reportsItems = sections.find((s) => s.section === "Reports")?.items ?? [];
  const systemItems = sections.find((s) => s.section === "System")?.items ?? [];
  // Admin's header splits Assessment/Monitoring into two dropdowns; examiner's keeps
  // them combined (unchanged). Same NAV items, just grouped differently at render time
  // rather than duplicated in the shared data.
  const monitoringItems = assessmentItems.filter(
    (i) => i.href.startsWith("/dashboard/proctoring") || i.href.startsWith("/dashboard/live"),
  );
  const adminAssessmentItems = assessmentItems.filter((i) => !monitoringItems.includes(i));
  const isActive = (href: string, isRoot = false) => {
    const path = href.split("?")[0];
    return isRoot ? pathname === path : pathname === path || pathname.startsWith(`${path}/`);
  };
  const assessmentActive = assessmentItems.some((i) => isActive(i.href));
  const peopleActive = peopleItems.some((i) => isActive(i.href));
  const adminAssessmentActive = adminAssessmentItems.some((i) => isActive(i.href));
  const monitoringActive = monitoringItems.some((i) => isActive(i.href));
  const reportsActive = reportsItems.some((i) => isActive(i.href));
  const systemActive = systemItems.some((i) => isActive(i.href));

  const navContent = (
    <nav className="flex flex-col gap-6 flex-1 overflow-y-auto px-3 py-5 dark-scroll">
      {sections.map((section, si) => (
        <div key={section.section}>
          <p className="mb-2 px-3 text-[9.5px] font-bold uppercase tracking-[0.14em]"
            style={{ color: "var(--color-sidebar-label)" }}>
            {sectionLabel(section.section)}
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
                    className="flex cursor-not-allowed items-center gap-3 rounded-[9px] px-3 py-2.5 text-[13px] opacity-35"
                    style={{ color: "var(--color-sidebar-text)" }}
                  >
                    <Icon size={15} />
                    <span className="flex-1">{navLabel(item)}</span>
                    <LockIcon />
                  </span>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cx(
                    "group relative flex items-center gap-3 rounded-[9px] px-3 py-2.5 text-[13px] font-medium transition-all duration-200",
                    active ? "nav-active-glow text-white" : "hover:text-white",
                  )}
                  style={active
                    ? {
                        background: "linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(79,70,229,0.15) 100%)",
                        color: "white",
                        border: "1px solid rgba(99,102,241,0.3)",
                        boxShadow: "0 2px 12px -4px rgba(79,70,229,0.35), inset 0 1px 0 rgba(255,255,255,0.05)",
                      }
                    : { color: "var(--color-sidebar-text)" }
                  }
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--color-sidebar-hover)"; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = ""; }}
                >
                  <Icon
                    size={15}
                    className={cx(active ? "text-white" : "text-[var(--color-sidebar-text)] group-hover:text-white")}
                  />
                  <span className="flex-1">{navLabel(item)}</span>
                  {item.badge === "AI" && (
                    <span className="rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white"
                      style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}>
                      AI
                    </span>
                  )}
                  {item.badge === "LIVE" && (
                    <span className="flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white"
                      style={{ background: "linear-gradient(135deg, #dc2626, #ef4444)" }}>
                      <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
                      LIVE
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
          {/* Section divider (skip after last section) */}
          {si < sections.length - 1 && (
            <div className="mt-5 h-px mx-3" style={{
              background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.05) 50%, transparent)",
            }} />
          )}
        </div>
      ))}
    </nav>
  );

  const sidebarBottom = (
    <div className="border-t px-3 py-3 shrink-0" style={{ borderColor: "var(--color-sidebar-border)" }}>
      {/* User card */}
      {/* The user card is the profile link now - there is no separate Profile entry. */}
      <Link
        href="/dashboard/profile"
        className="flex items-center gap-3 rounded-[11px] px-2.5 py-2.5 mb-1 transition-all hover:bg-white/5"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}
      >
        {/* Gradient avatar */}
        <div className={cx(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold text-white",
          `bg-gradient-to-br ${ROLE_GRADIENT[user.role]}`,
        )}>
          {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-white">{user.full_name}</p>
          <p className="truncate text-[11px]" style={{ color: "var(--color-sidebar-text)" }}>
            {roleLabel(user.role)}
          </p>
        </div>
      </Link>
      <button
        onClick={signOut}
        className="mt-1 flex w-full items-center gap-2.5 rounded-[8px] px-3 py-2 text-[12.5px] font-medium transition-all"
        style={{ color: "var(--color-sidebar-text)" }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(220,38,38,0.12)"; e.currentTarget.style.color = "#fca5a5"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = ""; e.currentTarget.style.color = "var(--color-sidebar-text)"; }}
      >
        <IconSignOut size={14} />
        {t("sign_out")}
      </button>
    </div>
  );

  // Shared by the examiner and admin headers - a dropdown panel under a nav trigger,
  // and the trigger's own button styling. Defined once here (component scope, not
  // inside either role branch) so admin's extra dropdown groups don't need a second copy.
  const dropdownPanel = (items: NavItem[], onNavigate: () => void) => (
    <div
      role="menu"
      className="animate-scale-in absolute left-0 top-full z-40 mt-1.5 w-60 origin-top overflow-hidden rounded-[10px] py-1.5 shadow-xl"
      style={{ background: "var(--color-sidebar)", border: "1px solid var(--color-sidebar-border)" }}
    >
      {items.map((item) => {
        const Icon = item.icon;
        const locked = Boolean(item.needsApproval) && !approved;
        const active = isActive(item.href);
        if (locked) {
          return (
            <span
              key={item.href}
              title="Awaiting administrator approval"
              className="flex cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] opacity-35"
              style={{ color: "var(--color-sidebar-text)" }}
            >
              <Icon size={14} />
              <span className="flex-1">{navLabel(item)}</span>
              <LockIcon />
            </span>
          );
        }
        return (
          <Link
            key={item.href}
            href={item.href}
            role="menuitem"
            onClick={onNavigate}
            className={cx(
              "flex items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium transition-colors",
              active ? "bg-white/10 text-white" : "hover:bg-white/5",
            )}
            style={{ color: active ? "white" : "var(--color-sidebar-text)" }}
          >
            <Icon size={14} />
            <span className="flex-1">{navLabel(item)}</span>
            {item.badge === "AI" && (
              <span className="rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white"
                style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}>
                AI
              </span>
            )}
            {item.badge === "LIVE" && (
              <span className="flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white"
                style={{ background: "linear-gradient(135deg, #dc2626, #ef4444)" }}>
                <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
                LIVE
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );

  const triggerClass = (active: boolean) =>
    cx(
      "flex items-center gap-1.5 rounded-[9px] px-4 py-2.5 text-[14.5px] font-medium transition-colors",
      active ? "bg-white/10 text-white" : "hover:bg-white/5",
    );

  if (isCandidate) {
    return (
      <div className="flex min-h-screen flex-col">
        {/* ───────── Candidate top header (nav lives here, no sidebar) ───────── */}
        <header className="sticky top-0 z-30 border-b border-line"
          style={{
            background: "rgba(245,246,250,0.85)",
            backdropFilter: "blur(20px) saturate(160%)",
            WebkitBackdropFilter: "blur(20px) saturate(160%)",
          }}>
          <div className="relative mx-auto flex h-16 w-full max-w-[1600px] items-center gap-4 px-4 lg:px-7">
            <div className="absolute inset-x-0 top-0 h-[2px]"
              style={{
                background: "linear-gradient(90deg, transparent, rgba(79,70,229,0.4) 30%, rgba(139,92,246,0.4) 70%, transparent)",
              }} />
            <div className="flex flex-1 items-center">
              <Brand />
            </div>
            <nav className="flex shrink-0 items-center gap-1 overflow-x-auto">
              {candidateNavItems.map((item) => {
                const Icon = item.icon;
                const isSectionRoot = item.href === "/dashboard/candidate";
                const active = isSectionRoot
                  ? pathname === item.href
                  : pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cx(
                      "flex shrink-0 items-center gap-2 rounded-[9px] px-3 py-2 text-[13px] font-medium transition-all whitespace-nowrap",
                      active ? "bg-accent text-white shadow-sm" : "text-ink-soft hover:bg-sunken hover:text-ink"
                    )}
                  >
                    <Icon size={14} />
                    {navLabel(item)}
                  </Link>
                );
              })}
            </nav>
            <div className="flex flex-1 items-center justify-end gap-2.5">
              <LanguageSelector />
              {!approved && (
                <Badge tone={user.access_status === "pending" ? "amber" : "rose"} size="xs">
                  {user.access_status === "pending" ? "Pending approval" : "Access revoked"}
                </Badge>
              )}
              <Link
                href="/dashboard/profile"
                title={approved ? "Your profile — Active" : "Your profile"}
                className={cx(
                  "hidden h-8 w-8 items-center justify-center rounded-full text-[12px] font-bold text-white shadow-sm transition-transform hover:scale-105 sm:flex",
                  `bg-gradient-to-br ${ROLE_GRADIENT[user.role]}`,
                  // The badge is gone - active status now reads as a glow on the avatar
                  // itself, rather than a separate word in the header. The avatar is
                  // also the profile link now - the wordmark next to it stays a plain logo.
                  approved &&
                    "ring-2 ring-green/70 ring-offset-2 ring-offset-paper shadow-[0_0_10px_2px_rgba(34,197,94,0.55)]",
                )}
              >
                {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
              </Link>
              <Button variant="ghost" size="sm" className="text-[12px]" onClick={signOut}>
                {t("sign_out")}
              </Button>
            </div>
          </div>
        </header>

        <main className="min-w-0 flex-1 px-4 py-4 lg:px-7 lg:py-5">
          <div className="mx-auto w-full max-w-[1600px] animate-rise">
            {children}
          </div>
        </main>
      </div>
    );
  }

  if (isExaminer) {
    return (
      <div className="flex min-h-screen flex-col">
        {/* ───────── Examiner top header: horizontal nav, dark theme ───────── */}
        <header
          ref={headerRef}
          className="sticky top-0 z-30 border-b"
          style={{ background: "var(--color-sidebar)", borderColor: "var(--color-sidebar-border)" }}
        >
          <div className="mx-auto flex h-[76px] w-full max-w-[1600px] items-center gap-2 px-4 lg:px-7">
            <div className="flex flex-1 items-center">
              <Link href="/dashboard/examiner" className="flex shrink-0 items-center">
                <Brand onDark />
              </Link>
            </div>

            {/* Desktop nav — centered in the header */}
            <nav className="hidden shrink-0 items-center gap-2 lg:flex">
              <Link
                href="/dashboard/examiner"
                className={triggerClass(isActive("/dashboard/examiner", true))}
                style={{ color: isActive("/dashboard/examiner", true) ? "white" : "var(--color-sidebar-text)" }}
              >
                {tc("dashboard")}
              </Link>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "assessment"}
                  onClick={() => setOpenMenu((m) => (m === "assessment" ? null : "assessment"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("assessment"); } }}
                  className={triggerClass(assessmentActive)}
                  style={{ color: assessmentActive || openMenu === "assessment" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_assessment")} <ChevronIcon open={openMenu === "assessment"} />
                </button>
                {openMenu === "assessment" && dropdownPanel(assessmentItems, () => setOpenMenu(null))}
              </div>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "people"}
                  onClick={() => setOpenMenu((m) => (m === "people" ? null : "people"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("people"); } }}
                  className={triggerClass(peopleActive)}
                  style={{ color: peopleActive || openMenu === "people" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_people")} <ChevronIcon open={openMenu === "people"} />
                </button>
                {openMenu === "people" && dropdownPanel(peopleItems, () => setOpenMenu(null))}
              </div>
            </nav>

            <div className="flex flex-1 items-center justify-end gap-1">
              {/* Mobile hamburger */}
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="flex h-9 w-9 items-center justify-center rounded-[8px] transition hover:bg-white/5 lg:hidden"
                style={{ color: "var(--color-sidebar-text)" }}
                aria-label="Open navigation"
              >
                <HamburgerIcon />
              </button>

              <LanguageSelector className="hidden lg:block" variant="dark" />

              {/* Notifications */}
              <Link
                href="/dashboard/login-requests"
                title={t("nav_login_requests")}
                className="hidden h-9 w-9 items-center justify-center rounded-[8px] transition hover:bg-white/5 lg:flex"
                style={{ color: "var(--color-sidebar-text)" }}
              >
                <BellIcon size={16} />
              </Link>

              {/* Profile: the avatar itself is a direct link, no dropdown needed. */}
              <Link
                href="/dashboard/profile"
                title="View profile"
                className="ml-1 hidden items-center gap-2.5 rounded-[9px] px-2 py-1.5 transition-colors hover:bg-white/5 lg:flex"
              >
                <Avatar name={user.full_name} src={user.avatar_url} size={34} shape="circle" />
                <span className="text-left">
                  <span className="block text-[13px] font-semibold leading-tight text-white">
                    {user.full_name}
                  </span>
                  <span className="block text-[11px] leading-tight" style={{ color: "var(--color-sidebar-text)" }}>
                    {roleLabel(user.role)}
                  </span>
                </span>
              </Link>

              <button
                type="button"
                onClick={signOut}
                title={tc("logout")}
                className="ml-1 hidden items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12.5px] font-medium text-rose-300 transition-colors hover:bg-rose-500/10 lg:flex"
              >
                <IconSignOut size={14} />
                {tc("logout")}
              </button>
            </div>
          </div>
        </header>

        {/* ───────── Mobile slide-over drawer (grouped, same as before) ───────── */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-ink/70 backdrop-blur-[3px] animate-fade" />
            <div
              ref={drawerRef}
              className="absolute inset-y-0 left-0 flex w-[268px] flex-col animate-slide-right"
              style={{ background: "var(--color-sidebar)", borderRight: "1px solid var(--color-sidebar-border)" }}
            >
              <div className="flex h-16 shrink-0 items-center gap-2.5 px-5"
                style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
                <Brand onDark />
                <button
                  onClick={() => setMobileOpen(false)}
                  className="ml-auto rounded-[7px] p-1.5 transition hover:bg-white/10"
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

        <main className="min-w-0 flex-1 px-4 py-6 lg:px-7 lg:py-7">
          <div className="mx-auto w-full max-w-[1600px] animate-rise">
            {children}
          </div>
        </main>
      </div>
    );
  }

  if (isAdmin) {
    return (
      <div className="flex min-h-screen flex-col">
        {/* ───────── Admin top header: global control-center nav, dark theme ───────── */}
        <header
          ref={headerRef}
          className="sticky top-0 z-30 border-b"
          style={{ background: "var(--color-sidebar)", borderColor: "var(--color-sidebar-border)" }}
        >
          <div className="mx-auto flex h-[76px] w-full max-w-[1600px] items-center gap-2 px-4 lg:px-7">
            <div className="flex flex-1 items-center">
              <Link href="/dashboard/admin" className="flex shrink-0 items-center">
                <Brand onDark />
              </Link>
            </div>

            {/* Desktop nav — centered in the header */}
            <nav className="hidden shrink-0 items-center gap-1.5 lg:flex">
              <Link
                href="/dashboard/admin"
                className={triggerClass(isActive("/dashboard/admin", true))}
                style={{ color: isActive("/dashboard/admin", true) ? "white" : "var(--color-sidebar-text)" }}
              >
                {tc("dashboard")}
              </Link>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "assessment"}
                  onClick={() => setOpenMenu((m) => (m === "assessment" ? null : "assessment"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("assessment"); } }}
                  className={triggerClass(adminAssessmentActive)}
                  style={{ color: adminAssessmentActive || openMenu === "assessment" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_assessment")} <ChevronIcon open={openMenu === "assessment"} />
                </button>
                {openMenu === "assessment" && dropdownPanel(adminAssessmentItems, () => setOpenMenu(null))}
              </div>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "monitoring"}
                  onClick={() => setOpenMenu((m) => (m === "monitoring" ? null : "monitoring"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("monitoring"); } }}
                  className={triggerClass(monitoringActive)}
                  style={{ color: monitoringActive || openMenu === "monitoring" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_monitoring")} <ChevronIcon open={openMenu === "monitoring"} />
                </button>
                {openMenu === "monitoring" && dropdownPanel(monitoringItems, () => setOpenMenu(null))}
              </div>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "people"}
                  onClick={() => setOpenMenu((m) => (m === "people" ? null : "people"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("people"); } }}
                  className={triggerClass(peopleActive)}
                  style={{ color: peopleActive || openMenu === "people" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_people")} <ChevronIcon open={openMenu === "people"} />
                </button>
                {openMenu === "people" && dropdownPanel(peopleItems, () => setOpenMenu(null))}
              </div>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "reports"}
                  onClick={() => setOpenMenu((m) => (m === "reports" ? null : "reports"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("reports"); } }}
                  className={triggerClass(reportsActive)}
                  style={{ color: reportsActive || openMenu === "reports" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_reports")} <ChevronIcon open={openMenu === "reports"} />
                </button>
                {openMenu === "reports" && dropdownPanel(reportsItems, () => setOpenMenu(null))}
              </div>

              <div className="relative">
                <button
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={openMenu === "system"}
                  onClick={() => setOpenMenu((m) => (m === "system" ? null : "system"))}
                  onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setOpenMenu("system"); } }}
                  className={triggerClass(systemActive)}
                  style={{ color: systemActive || openMenu === "system" ? "white" : "var(--color-sidebar-text)" }}
                >
                  {t("section_system")} <ChevronIcon open={openMenu === "system"} />
                </button>
                {openMenu === "system" && dropdownPanel(systemItems, () => setOpenMenu(null))}
              </div>
            </nav>

            <div className="flex flex-1 items-center justify-end gap-1">
              {/* Mobile hamburger */}
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="flex h-9 w-9 items-center justify-center rounded-[8px] transition hover:bg-white/5 lg:hidden"
                style={{ color: "var(--color-sidebar-text)" }}
                aria-label="Open navigation"
              >
                <HamburgerIcon />
              </button>

              <LanguageSelector className="hidden lg:block" variant="dark" />

              {/* Notifications */}
              <Link
                href="/dashboard/login-requests"
                title={t("nav_login_requests")}
                className="hidden h-9 w-9 items-center justify-center rounded-[8px] transition hover:bg-white/5 lg:flex"
                style={{ color: "var(--color-sidebar-text)" }}
              >
                <BellIcon size={16} />
              </Link>

              {/* Profile: the avatar itself is a direct link, no dropdown needed. */}
              <Link
                href="/dashboard/profile"
                title="View profile"
                className="ml-1 hidden items-center gap-2.5 rounded-[9px] px-2 py-1.5 transition-colors hover:bg-white/5 lg:flex"
              >
                <Avatar name={user.full_name} src={user.avatar_url} size={34} shape="circle" />
                <span className="text-left">
                  <span className="block text-[13px] font-semibold leading-tight text-white">
                    {user.full_name}
                  </span>
                  <span className="block text-[11px] leading-tight" style={{ color: "var(--color-sidebar-text)" }}>
                    {roleLabel(user.role)}
                  </span>
                </span>
              </Link>

              <button
                type="button"
                onClick={signOut}
                title={tc("logout")}
                className="ml-1 hidden items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12.5px] font-medium text-rose-300 transition-colors hover:bg-rose-500/10 lg:flex"
              >
                <IconSignOut size={14} />
                {tc("logout")}
              </button>
            </div>
          </div>
        </header>

        {/* ───────── Mobile slide-over drawer (grouped, same as before) ───────── */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-ink/70 backdrop-blur-[3px] animate-fade" />
            <div
              ref={drawerRef}
              className="absolute inset-y-0 left-0 flex w-[268px] flex-col animate-slide-right"
              style={{ background: "var(--color-sidebar)", borderRight: "1px solid var(--color-sidebar-border)" }}
            >
              <div className="flex h-16 shrink-0 items-center gap-2.5 px-5"
                style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
                <Brand onDark />
                <button
                  onClick={() => setMobileOpen(false)}
                  className="ml-auto rounded-[7px] p-1.5 transition hover:bg-white/10"
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

        <main className="min-w-0 flex-1 px-4 py-6 lg:px-7 lg:py-7">
          <div className="mx-auto w-full max-w-[1600px] animate-rise">
            {children}
          </div>
        </main>
      </div>
    );
  }

  // Unreachable in practice - candidate/examiner/admin are the only roles and each has
  // its own branch above. Kept as a defensive fallback, not deleted, in case a role is
  // ever added without a dedicated header.
  return (
    <div className="flex min-h-screen">
      {/* ───────── Desktop sidebar ───────── */}
      <aside
        className="relative hidden w-[248px] shrink-0 flex-col lg:flex"
        style={{
          background: "var(--color-sidebar)",
          borderRight: "1px solid var(--color-sidebar-border)",
        }}
      >
        {/* Subtle top glow */}
        <div className="absolute top-0 left-0 right-0 h-32 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.12) 0%, transparent 70%)",
          }} />

        {/* Logo */}
        <div className="flex h-16 shrink-0 items-center px-5"
          style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
          <Brand onDark />
        </div>

        {navContent}
        {sidebarBottom}
      </aside>

      {/* ───────── Mobile slide-over drawer ───────── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/70 backdrop-blur-[3px] animate-fade" />
          <div
            ref={drawerRef}
            className="absolute inset-y-0 left-0 flex w-[268px] flex-col animate-slide-right"
            style={{ background: "var(--color-sidebar)", borderRight: "1px solid var(--color-sidebar-border)" }}
          >
            <div className="flex h-16 shrink-0 items-center gap-2.5 px-5"
              style={{ borderBottom: "1px solid var(--color-sidebar-border)" }}>
              <Brand onDark />
              <button
                onClick={() => setMobileOpen(false)}
                className="ml-auto rounded-[7px] p-1.5 transition hover:bg-white/10"
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
        {/* Top header — glassmorphic */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-line px-4 lg:px-6"
          style={{
            background: "rgba(245,246,250,0.85)",
            backdropFilter: "blur(20px) saturate(160%)",
            WebkitBackdropFilter: "blur(20px) saturate(160%)",
          }}>
          {/* Top accent line */}
          <div className="absolute inset-x-0 top-0 h-[2px]"
            style={{
              background: "linear-gradient(90deg, transparent, rgba(79,70,229,0.4) 30%, rgba(139,92,246,0.4) 70%, transparent)",
            }} />

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="flex h-8 w-8 items-center justify-center rounded-[9px] border border-line text-ink-soft hover:bg-sunken hover:border-accent/30 transition lg:hidden"
              aria-label="Open navigation"
            >
              <HamburgerIcon />
            </button>
            {/* Greeting */}
            <div className="hidden sm:block">
              <p className="text-[13.5px] font-bold text-ink">
                {greeting()},{" "}
                <span style={{
                  background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}>
                  {user.full_name.split(" ")[0]}
                </span>{" "}
                👋
              </p>
              <p className="text-[11px] text-ink-muted font-medium">{roleLabel(user.role)} {t("workspace")}</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <LanguageSelector />
            {/* Access status badge */}
            {user.role !== "admin" && !approved && (
              <Badge tone={user.access_status === "pending" ? "amber" : "rose"} size="xs">
                {user.access_status === "pending" ? "Pending approval" : "Access revoked"}
              </Badge>
            )}
            {user.role !== "admin" && approved && (
              <Badge tone="green" size="xs">Active</Badge>
            )}
            {/* User avatar with gradient */}
            <div className={cx(
              "flex h-8 w-8 items-center justify-center rounded-full text-[12px] font-bold text-white shadow-sm",
              `bg-gradient-to-br ${ROLE_GRADIENT[user.role]}`,
            )}>
              {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
            </div>
            {/* Mobile sign out */}
            <Button variant="ghost" size="sm" className="lg:hidden text-[12px]" onClick={signOut}>
              {t("sign_out")}
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

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden
      className={cx("shrink-0 transition-transform duration-150", open && "rotate-180")}
    >
      <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
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
