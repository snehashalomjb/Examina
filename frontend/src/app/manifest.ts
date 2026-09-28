import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Examina — AI-Proctored Examination Platform",
    short_name: "Examina",
    description:
      "Secure online assessment with question pools, randomized papers, timed sittings, AI proctoring, and multilingual exam support.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    background_color: "#181b2e",
    theme_color: "#181b2e",
    orientation: "any",
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
  };
}
