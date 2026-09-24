"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Splash, useSplashText } from "@/components/Splash";
import { homeFor, useAuth } from "@/lib/auth";

/** /dashboard has no content of its own - it forwards to the role's own dashboard. */
export default function DashboardIndex() {
  const { user, booting } = useAuth();
  const router = useRouter();
  const text = useSplashText();

  useEffect(() => {
    if (booting) return;
    router.replace(user ? homeFor(user) : "/login");
  }, [user, booting, router]);

  return <Splash label={text("splash_opening_dashboard")} />;
}
