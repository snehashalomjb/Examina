import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { AuthProvider } from "@/lib/auth";
import { LocaleProvider } from "@/lib/locale";
import { ToastHost } from "@/components/ui";
import { ServiceWorkerRegister } from "@/components/ServiceWorkerRegister";
import "./globals.css";

/**
 * Plus Jakarta Sans carries the product voice: a little more character than Inter in
 * headings, still neutral enough for a table of marks. Loaded as a variable font so the
 * whole 400-800 range costs one file, which is what the heading/body/caption hierarchy
 * in globals.css spends.
 */
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Examina — AI-Proctored Examination Platform",
  description:
    "Question banks, randomized papers, timed exams with AI proctoring, and examiner-reviewed grading.",
  applicationName: "Examina",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Examina",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

/** Explicit so the layout scales on a phone and clears a notched screen. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#181b2e",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // Browser extensions (Grammarly, ColorZilla, password managers) inject attributes
    // like data-gr-ext-installed or cz-shortcut-listen onto <html>/<body> before React
    // hydrates. That is a mismatch React cannot fix and should not warn about - it is
    // not a bug in this app, so it is silenced here rather than by suppressing every
    // hydration warning in the tree.
    <html lang="en" className={jakarta.variable} suppressHydrationWarning>
      <body className="min-h-screen antialiased" suppressHydrationWarning>
        <ServiceWorkerRegister />
        <LocaleProvider>
          <AuthProvider>
            {children}
            <ToastHost />
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}

