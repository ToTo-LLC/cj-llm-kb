/** @type {import('next').NextConfig} */
// Plan 08 Task 2 — static export. brain_api serves ``apps/brain_web/out/``
// under ``/`` with SPA fallback, so the steady-state runtime on a user's box
// is one uvicorn process (no Node). ``trailingSlash`` keeps directory-style
// URLs (``/chat/`` → ``/chat/index.html``) that match static file layout;
// the SPA fallback on the backend catches anything else.
//
// In ``next dev`` mode (port 4316) the static export setting is ignored and
// we add a rewrite that proxies ``/api/*`` and ``/ws/*`` to a separately
// running brain_api on port 4317. Production builds use ``output: "export"``
// (above) and never see the rewrite, so this is dev-only plumbing — it lets
// designer-iteration sessions hit the dev server with HMR while still
// reaching real backend endpoints.
const isDev = process.env.NODE_ENV !== "production";
const BRAIN_API_PROXY =
  process.env.BRAIN_API_PROXY ?? "http://127.0.0.1:4317";

const nextConfig = {
  reactStrictMode: true,
  // Static export only in production — ``next dev`` ignores it but the
  // rewrites below would error if both were active simultaneously.
  ...(isDev ? {} : { output: "export" }),
  images: { unoptimized: true },
  trailingSlash: true,
  ...(isDev
    ? {
        async rewrites() {
          return [
            { source: "/api/:path*", destination: `${BRAIN_API_PROXY}/api/:path*` },
            { source: "/ws/:path*", destination: `${BRAIN_API_PROXY}/ws/:path*` },
            { source: "/healthz", destination: `${BRAIN_API_PROXY}/healthz` },
          ];
        },
      }
    : {}),
};

export default nextConfig;
