# Deploying SereneVibes to Vercel

## Architecture
- Flask backend (Python) — serves API + static files + generates PDFs
- React admin panel (Vite) — built by Vercel at deploy time
- PostgreSQL (Neon recommended) — set via `DATABASE_URL` env var

## One-time Setup

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "initial"
git remote add origin https://github.com/YOUR_USERNAME/serenevibes.git
git push -u origin main
```

### 2. Import project in Vercel
- Go to https://vercel.com/new
- Import your GitHub repo
- **Framework Preset**: leave as "Other"
- **Root Directory**: leave as `.` (project root)
- Click **Deploy** — Vercel reads `vercel.json` automatically

### 3. Set Environment Variables
In your Vercel project → Settings → Environment Variables, add:

| Variable         | Value                                      |
|------------------|--------------------------------------------|
| `DATABASE_URL`   | Your PostgreSQL URL (e.g. from Neon)       |
| `SECRET_KEY`     | A long random string                       |
| `ADMIN_PASSWORD` | Your admin panel password                  |

> **Recommended DB**: [Neon](https://neon.tech) — free PostgreSQL, works great with Vercel.
> Copy the connection string from Neon; it starts with `postgresql://`.

#### Optional: AI Kashmir Travel Assistant
The "Ask our Kashmir Travel Assistant" chat button only appears once this key is set:

| Variable         | Value                                                                    |
|------------------|--------------------------------------------------------------------------|
| `GROQ_API_KEY`   | API key from https://console.groq.com/keys (starts with `gsk_`)          |

Optional tuning (sensible defaults are built in):

| Variable                     | Default                       | Meaning                                        |
|------------------------------|-------------------------------|------------------------------------------------|
| `ASSISTANT_MODEL`            | `openai/gpt-oss-120b`         | Which Groq model answers visitors (must support tool calling; `openai/gpt-oss-20b` is cheaper/faster) |
| `ASSISTANT_TIMEOUT`          | `9`                           | Seconds to wait for the model (Vercel Hobby functions stop at 10s) |
| `ASSISTANT_HOURLY_LIMIT`     | `25`                          | Messages per visitor per hour                  |
| `ASSISTANT_DAILY_LIMIT`      | `80`                          | Messages per visitor per day                   |
| `ASSISTANT_SITE_DAILY_CAP`   | `1500`                        | Messages across all visitors per day (cost guard) |

After deploying, open `/admin` -> **AI Assistant** to switch it on/off and add your real rates
(budget tiers, child pricing, peak-season charges). The assistant only quotes prices from your
Packages and those notes. Chats are not stored; only a hashed IP is kept for rate limiting.

### 4. Redeploy
After adding env vars, trigger a redeploy from the Vercel dashboard.

## Important Notes

### PDF file storage
Vercel's filesystem is **read-only** except `/tmp`. PDFs are written to `/tmp/output/`
and served via `/output/<filename>`. They are **ephemeral** — they disappear when
the serverless function cold-starts. For production, consider streaming PDFs directly
in the response rather than saving to disk, or use a storage service (S3, Cloudflare R2).

### Cold starts
Vercel runs Flask as a serverless function. The first request after inactivity may
take 2–4 seconds. Subsequent requests are fast.

### Admin panel
Built automatically by Vercel at deploy time (`vite build` in `/admin`).
Available at `https://your-app.vercel.app/admin`

## Local Development (unchanged)
```bash
# Terminal 1 — Flask backend
pip install -r requirements.txt
python -m flask --app backend.app run --port 5000

# Terminal 2 — Admin React dev server
cd admin && npm install && npm run dev
```
