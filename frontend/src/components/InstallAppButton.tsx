"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui";

const DISMISS_KEY = "examina-install-dismissed";

/** Chrome/Edge fire this instead of the standard Event shape; not in lib.dom.d.ts. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // iOS Safari's own installed-PWA flag; not in the standard Navigator type.
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/**
 * Reusable "Install App" banner. Renders nothing until the browser actually
 * fires beforeinstallprompt, and disappears again once installed or dismissed
 * for this browser - there is no reliable "is it installable" check up front.
 */
export function InstallAppButton() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone() || sessionStorage.getItem(DISMISS_KEY) === "1") {
      return;
    }

    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setDeferredPrompt(event as BeforeInstallPromptEvent);
      setVisible(true);
    };
    const onAppInstalled = () => {
      setDeferredPrompt(null);
      setVisible(false);
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  if (!visible || !deferredPrompt) return null;

  const handleInstall = async () => {
    try {
      await deferredPrompt.prompt();
      await deferredPrompt.userChoice;
    } finally {
      setDeferredPrompt(null);
      setVisible(false);
    }
  };

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, "1");
    setVisible(false);
  };

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-[150] flex justify-center px-4">
      <div className="pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-[13px] border border-line bg-surface px-4 py-3 shadow-[var(--shadow-lift)]">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-ink">Install Examina</p>
          <p className="text-[12px] text-ink-muted">Add it to your home screen for quick access.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={handleDismiss}>
          Not now
        </Button>
        <Button size="sm" onClick={handleInstall}>
          Install
        </Button>
      </div>
    </div>
  );
}
