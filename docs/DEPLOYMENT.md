# GasDex Deployment Guide

Complete step-by-step checklist for the maintainer to go live with GitHub Pages or Cloudflare Pages.

## Prerequisites

- GitHub account
- A domain name (optional; free github.io subdomain works initially)
- DNS access if using a custom domain

## Option A: GitHub Pages (Recommended for simplicity)

### 1. Create GitHub repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `gasdex` (recommended)
3. **Make it PUBLIC** (required for free GitHub Pages)
4. Do **NOT** initialize with a README / .gitignore / licence — the project already
   has them, and an initialized repo would conflict with the first push
5. Click **Create repository**

### 2. Push this codebase

From your local machine (with this directory as the working directory):

```bash
git init
git add .
git commit -m "Initial commit: GasDex static site generator"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub username and repository name.

### 3. Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** (top-right menu)
3. Scroll left sidebar → **Pages**
4. Under "Build and deployment":
   - **Source**: Select **GitHub Actions**
   - (The `build.yml` workflow will now be the deployment source)
5. Click **Save**

### 4. Trigger first build

1. Go to **Actions** tab (top of repository)
2. On the left, click **Build & Deploy GasDex** workflow
3. Click **Run workflow** → **Run workflow** (blue button)
4. Wait ~2 minutes for the build to complete
5. After success, your site is live at:
   - `https://YOUR_USERNAME.github.io/YOUR_REPO/` (if repo name is not your username)
   - `https://YOUR_USERNAME.github.io/` (if repo is named `YOUR_USERNAME`)

### 5. Custom domain (optional)

To use a custom domain (e.g., `gasdex.co.uk`):

1. **Buy & verify domain** at your registrar (e.g., Namecheap, GoDaddy, Route53)
2. In repository **Settings** → **Pages**:
   - Enter custom domain in the **Custom domain** field
   - Check **Enforce HTTPS**
3. At your domain registrar, update **DNS records**:
   - If using apex domain (`gasdex.co.uk`):
     ```
     Type: A
     Name: @
     Value: 185.199.108.153
            185.199.109.153
            185.199.110.153
            185.199.111.153
     ```
   - If using subdomain (`www.gasdex.co.uk`):
     ```
     Type: CNAME
     Name: www
     Value: YOUR_USERNAME.github.io
     ```
4. Wait for DNS to propagate (5 minutes to 48 hours)
5. GitHub will auto-create a CNAME file in your repo and enable HTTPS

See [GitHub's custom domain guide](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages) for full details.

## Option B: Cloudflare Pages

If you prefer Cloudflare (faster, more control, free tier):

### 1. Create Cloudflare Pages project

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Click **Pages** (left sidebar)
3. Click **Create a project** → **Connect to Git**
4. Authorize GitHub, select this repository
5. On the configuration page:
   - **Production branch**: `main`
   - **Build command**: (leave empty — we use GitHub Actions)
   - **Build output directory**: `out/`
6. Click **Save and Deploy**

### 2. Update GitHub Actions workflow

Modify `.github/workflows/build.yml` to upload to Cloudflare instead:

Replace the GitHub Pages deployment step with:

```yaml
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: YOUR_PROJECT_NAME
          directory: out/
          productionBranch: main
```

Then add secrets to GitHub:
1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Add:
   - `CLOUDFLARE_API_TOKEN` (from Cloudflare dashboard)
   - `CLOUDFLARE_ACCOUNT_ID` (from Cloudflare dashboard)

### 3. Custom domain (Cloudflare)

1. Add your domain to Cloudflare (free)
2. In Cloudflare **Pages** project settings:
   - Click **Custom domain**
   - Enter your domain
   - Cloudflare will guide you through DNS setup

---

## Monitoring & Maintenance

### Check build status

1. Go to **Actions** tab in GitHub
2. Click the most recent run to see logs
3. If a feed fetcher fails (marked as "continue-on-error"), the site still builds with fallback data — check logs to diagnose

### Rebuild history cache issue

The rolling caches (`data/results-history.json`, `data/news-history.json`,
`data/fixtures-audit.json`) accumulate across builds. Since the session-13
git fix they live on the dedicated **`data-cache` branch** (written ONLY by
CI — never by hand, never on main; they are gitignored on main so the
maintainer's pushes can never conflict with the hourly bot commits).

- The canonical copies: `https://github.com/marrowsplat/gasdex/tree/data-cache/data`
- If a cache is ever corrupted, restore it from that branch's history:
  ```bash
  git fetch origin data-cache:refs/remotes/origin/data-cache
  git checkout origin/data-cache~1 -- data/results-history.json
  ```
  then commit the fixed file back to the data-cache branch (a job for
  Claude, not the maintainer).
- NEVER delete the data-cache branch — it holds irreplaceable history.

### Change rebuild frequency

Edit `.github/workflows/build.yml`, line with the cron schedule:

```yaml
  schedule:
    - cron: '0 */3 * * *'  # Every 3 hours
```

Common alternatives:
- `'0 */6 * * *'` — Every 6 hours
- `'0 0 * * *'` — Daily at midnight UTC
- `'0 12 * * 0'` — Weekly Sunday at noon UTC
- `'*/30 * * * *'` — Every 30 minutes (note: GitHub may throttle frequent runs)

Push the updated workflow, and the new schedule takes effect immediately.

### Fix a failed run

If a GitHub Actions run fails:

1. Go to **Actions** → click the failed run
2. Click the failing step to see logs
3. Common issues:
   - **Feed timeout** (network/API down): Next run will retry automatically
   - **Invalid JSON in data/**: Check fetcher scripts for bugs
   - **Template not found**: Verify file structure (templates/index.template.html exists)
4. Fix locally, push to main, or manually re-trigger:
   - Click **Re-run failed jobs** or **Run workflow**

### Update site content

**Design changes**: Edit `site/index.html` and mirror changes to `templates/index.template.html` (keep them in sync).

**Data structure changes**: Update the fetcher scripts (tools/feeds/) and rebuild.

**Internal pages**: Edit `site/report-example.html`, `site/rate.html`, etc., then re-run workflow (the build step copies them to out/).

---

## Upgrading to paid data (optional)

### Switch to API-Football for results

If you want more detailed stats or higher request volume:

1. Create account at [api-sports.io](https://api-sports.io)
2. Subscribe to the football API ($19/month minimum; 300 req/day)
3. Copy your API key
4. Add GitHub secret: **Settings** → **Secrets** → `API_FOOTBALL_KEY`
5. Edit `tools/feeds/fetch_results.py`: Set `USE_API_FOOTBALL = True` at the top
6. Deploy (commit and push)

---

## Troubleshooting

### "PROTOTYPE banner" still shows

This means one or more feeds have `"sample": true` in their JSON output. Common causes:
- Feed fetcher timed out (network issue) → retried next build, usually resolves
- Invalid feed URL or RSS broken → check `tools/feeds/common.py` + the specific fetcher

The site remains fully functional with fallback data.

### Build is slow

The workflow has a 2-minute timeout per fetcher (4 feeds × 2 min = ~8 min total). If a feed is timing out:
1. Check GitHub Actions logs
2. Check if the remote feed is down (test URL manually)
3. Consider disabling that fetcher temporarily in `.github/workflows/build.yml`

### Results "Last 5" is empty

If results haven't populated after the first build:
1. This is expected if TheSportsDB returns no matches (e.g., off-season)
2. After a few match weeks, `data/results-history.json` accumulates (on the
   `data-cache` branch) and the display fills in
3. To seed with manual data: edit `data/results-history.json` on the
   `data-cache` branch and commit there (a job for Claude, not the maintainer)

### CNAME file disappeared

If custom domain is broken after a push:
1. Check `.github/workflows/build.yml` — if it deletes the `out/` directory before copying files, the CNAME is lost
2. Cloudflare/GitHub will recreate it, but there's a brief outage
3. **Fix**: Ensure the workflow uses `mkdir -p out` (not `rm -rf out`)

---

## Security notes

- **No API keys in code**: TheSportsDB needs no key; API-Football key is stored as a GitHub secret, not in the repo
- **Bot commits go to the `data-cache` branch, never main** (session-13 fix): the workflow commits the rolling caches there, so it can't trigger itself (the push trigger only watches main) and can't conflict with the maintainer's pushes
- **GitHub Actions permissions**: Workflow file limits permissions to `contents: write` (commit), `pages: write`, and `id-token: write` (deploy)

---

## Going live checklist

- [ ] Repository created and pushed
- [ ] GitHub Pages enabled (or Cloudflare Pages configured)
- [ ] First build successful (check Actions tab)
- [ ] Site accessible at deploy URL
- [ ] Domain purchased (if using custom domain)
- [ ] DNS configured (if using custom domain)
- [ ] Feed fetchers producing real data (check data/*.json)
- [ ] Build schedule set (default: hourly)
- [ ] Bookmarked for daily checks!

---

## Questions?

Check these docs:
- **Technical details**: [build-notes.md](build-notes.md) (site generator), [feeds-notes.md](feeds-notes.md) (fetchers)
