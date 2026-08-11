import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // lib/metrics.ts reads its JSON at request time from a path built out of an
  // env var. Next's dependency tracer only follows static imports, so without
  // this the serverless bundle ships WITHOUT the data file and the deployed
  // page fails with ENOENT. Verified via .next/server/app/page.js.nft.json.
  // Only the synthetic sample is listed — the real metrics.json is never
  // bundled, even if it exists locally at build time.
  outputFileTracingIncludes: {
    "/": ["./data/sample.metrics.json"],
  },
};

export default nextConfig;
