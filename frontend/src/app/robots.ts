import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? "https://stock-intelligence.app";
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/backtest"],
        disallow: ["/api/", "/account", "/billing", "/stocks/"],
      },
    ],
    sitemap: `${site}/sitemap.xml`,
  };
}
