import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { AuthProvider } from "@/lib/auth";
import { ToastHost } from "@/components/ui";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Examina — AI-Proctored Examination Platform",
  description:
    "Question banks, randomized papers, timed exams with AI proctoring, and examiner-reviewed grading.",
};

/** Explicit so the layout scales on a phone and clears a notched screen. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen antialiased">
        <AuthProvider>
          {children}
          <ToastHost />
        </AuthProvider>
      </body>
    </html>
  );
}
