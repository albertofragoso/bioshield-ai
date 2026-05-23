import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_BASE_URL ?? "https://bioshield.mx";
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/privacy", "/terms", "/api/og"],
        disallow: ["/home", "/scan", "/biosync", "/history", "/login", "/register"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
