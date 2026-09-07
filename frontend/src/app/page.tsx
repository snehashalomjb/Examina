"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Splash } from "@/components/Splash";
import { homeFor, useAuth } from "@/lib/auth";

/**
 * Entry point: hold the splash until the session resolves, then send the user to the
 * dashboard their role owns - or to sign-in.
 */
export default function Home() {
  const { user, booting } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (booting) return;
    router.replace(user ? homeFor(user) : "/login");
  }, [user, booting, router]);

  return <Splash label={booting ? "Preparing your workspace" : "Taking you there"} />;
}
