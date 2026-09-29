import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Examina — AI-Proctored Examination Platform",
    short_name: "Examina",
    description:
      "Secure online assessment with question pools, randomized papers, timed sittings, AI proctoring, and multilingual exam support.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    // Richer display modes tried in order; falls back to "standalone" on
    // browsers that don't support window-controls-overlay yet.
    display_override: ["window-controls-overlay", "standalone", "minimal-ui"],
    background_color: "#181b2e",
    theme_color: "#181b2e",
    orientation: "any",
    // App store / discovery categorisation
    categories: ["education", "productivity", "utilities"],
    // Prevent the browser from recommending a native app instead of this PWA
    prefer_related_applications: false,
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-192-maskable.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icons/icon-512-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    // Rich install UI: browser shows these in the "Add to Home Screen" sheet
    screenshots: [
      {
        src: "/screenshots/screenshot-wide.jpg",
        sizes: "1366x768",
        type: "image/jpeg",
        form_factor: "wide",
        label: "Examina Dashboard — manage and monitor all your exams",
      },
      {
        src: "/screenshots/screenshot-mobile.jpg",
        sizes: "390x844",
        type: "image/jpeg",
        form_factor: "narrow",
        label: "Examina on mobile — your exams on the go",
      },
    ],
  };
}

