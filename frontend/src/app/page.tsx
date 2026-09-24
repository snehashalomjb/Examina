"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Splash, useSplashText } from "@/components/Splash";
import { homeFor, useAuth } from "@/lib/auth";

/**
 * Entry point: hold the splash until the session resolves, then send the user to the
 * dashboard their role owns - or to sign-in.
 */
export default function Home() {
  const { user, booting } = useAuth();
  const router = useRouter();
  const text = useSplashText();

  useEffect(() => {
    if (booting) return;
    router.replace(user ? homeFor(user) : "/login");
  }, [user, booting, router]);

  return <Splash label={booting ? text("splash_preparing") : text("splash_taking_you_there")} />;
}
