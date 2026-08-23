# Deploying the frontend on Vercel

This folder's `web/index.html` is a single static file that talks to the
attendance backend over HTTP, so it can be deployed to Vercel even though the
backend (InsightFace pipeline) keeps running on Railway.

## One-step deploy

1. Log in to [vercel.com](https://vercel.com/) -> Dashboard -> New Project.
2. Import your Git repo: **GitHub -> `Sanket-sourav/FACEID2`**.
3. On the **"Configure Project"** screen set:
   - **Root Directory** = `web`  (so only the frontend is served; secrets/, data/, src/
     are excluded automatically)
   - **Build Command** = _(leave blank; Vercel auto-detects a static site)_
   - **Output Directory** = _(leave blank)_
4. Click **Deploy**. First deploy is instant (one static file).

## Point the frontend at your backend (replace the placeholder once)

Edit [`web/vercel.json`](https://github.com/Sanket-sourav/FACEID2/blob/main/web/vercel.json)
and replace `<YOUR-RAILWAY-BACKEND>.railway.app` with your real Railway app domain
(found in your Railway project -> Settings -> Public Domain), e.g.
`https://attendance-api.up.railway.app`:

```jsonc
{
  "version": 3,
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://attendance-api.up.railway.app/api/$1" },
    { "source": "/health",    "destination": "https://attendance-api.up.railway.app/health" }
  ]
}
```

These **rewrites** are Vercel server-side proxies: the browser still calls
`/api/...` and `/health`, which Vercel forwards to your Railway backend. Push to
`main` to redeploy; then test:

```bash
curl https://YOUR-APP.vercel.app/health   # should return your backend JSON
```

## Configure backend auth (so the login page appears)

Set these on your Railway project (Railway -> Settings -> Variables):
- `ATTENDANCE_TEACHER_USERNAME`, `ATTENDANCE_TEACHER_PASSWORD` (enables login)
- `ATTENDANCE_SHEET_ID`, `ATTENDANCE_CREDENTIALS_JSON` (writes to your Sheet)

When those teacher creds are set, `/health` returns `login_configured: true` and
the frontend shows the **Teacher login** card. (Left unset, the frontend shows the
open-mode "Continue as Guest" banner instead.)

## Login vs Guest vs Print

- **Login** -> POST /api/login -> bearer token -> take attendance (upload video).
- **Use as Guest** -> skip login, upload straight to the open-mode backend.
- After results render, **Print attendance** (and the @media print stylesheet)
  produce a printer-friendly attendance sheet (roster + summary + Sheet status).

## Advanced: set the backend URL at runtime instead of editing vercel.json

`web/index.html` also honours `window.ATTENDANCE_API_BASE` (absolute URL, overrides
the rewrites). This needs a build step to inject it on Vercel static hosting, so
the `vercel.json` rewrite above is the recommended default. Leave it unset to use
same-origin (relative) calls (local dev / co-hosted).
