/** @type {import('next').NextConfig} */
// Plan 08 Task 2 — static export. brain_api serves ``apps/brain_web/out/``
// under ``/`` with SPA fallback, so the steady-state runtime on a user's box
// is one uvicorn process (no Node). ``trailingSlash`` keeps directory-style
// URLs (``/chat/`` → ``/chat/index.html``) that match static file layout;
// the SPA fallback on the backend catches anything else.
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
