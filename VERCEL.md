# Deploying the frontend on Vercel

This folder's `web/index.html` is a single static file that talks to the
attendance backend over HTTP, so it can be deployed to Vercel even though the
backend (InsightFace pipeline) keeps running on Railway.

## One-step deploy

1. Push this repo to GitHub (or import the repo directly into Vercel).
2. In the Vercel dashboard, create a new project from the repo.
3. Set **Root Directory** to `web` (so only the frontend is served), **or** leave it
   at the repo root — `vercel.json` + `.vercelignore` already scope the deploy to `web/`
   and keep `secrets/`, `data/`, `src/` out.
4. Vercel auto-detects a static site (no build command needed) and deploys.

## Point the frontend at your backend

Edit the `destination` URLs in the root `vercel.json` and replace
`<YOUR-RAILWAY-BACKEND>.railway.app` with your actual Railway app URL, then redeploy.

- `vercel.json` rewrites `/api/*` and `/health` to your backend (server-side proxy),
  so the frontend's relative calls work from `your-app.vercel.app`.
- If you prefer to set the backend at runtime instead, add the env var
  `ATTENDANCE_API_BASE` (absolute URL) — the frontend reads
  `window.ATTENDANCE_API_BASE` automatically. Leave it unset to use same-origin
  (relative) calls (local dev / co-hosted).

## Login vs Guest

- Teacher login uses your backend `ATTENDANCE_TEACHER_USERNAME`/`ATTENDANCE_TEACHER_PASSWORD`.
- "Use as Guest" skips login (no token). Works fully when the backend runs in
  open mode; if the backend requires auth, the upload will 401 and prompt to log in.
- After results render, the "🖨️ Print attendance" button and an `@media print`
  stylesheet produce a printer-friendly attendance sheet.
