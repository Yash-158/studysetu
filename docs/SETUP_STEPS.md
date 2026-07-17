# SETUP_STEPS.md - From Empty Windows 11 Laptop to Ready-to-Code
The definitive pre-implementation guide. Follow top to bottom. Every step says WHAT, WHY in plain language, WHY NOW, and the exact commands. When this document is complete, Phase 0 of PHASES.md is done and feature work may begin.

> **Amendment (M0 domain integration, current):** this is retained as historical/onboarding narrative (predates the product name freeze and the multi-project droplet decision). Where this doc describes Caddy living inside this project's compose, or a `~/app` deploy path, or a placeholder domain: those are superseded by docs/DEPLOYMENT.md, docs/ARCHITECTURE.md ADR-011, and infra/droplet-bootstrap.sh. Current facts: domain `caffeineclause.tech` (flat subdomains `studysetu.` / `studysetu-api.`), droplet 64.227.177.181, deploy path `/home/deploy/studysetu`, shared edge layer in the separate `caffeineclause-edge` repo.

Companion documents: README_BIBLE.md (decisions and rationale), CLAUDE.md (Claude Code behavior), docs/PHASES.md (what happens after this guide).

---

# PART A - The Complete Service and Tool Inventory

| # | Service / Tool | Purpose | Why this one | Mandatory? | Cost source | Create when | Rejected alternatives (why) |
|---|---|---|---|---|---|---|---|
| 1 | **GitHub** | Repo, CI/CD (Actions), container registry (GHCR), secrets | One platform covers code, pipeline, and image registry; team already fluent | MANDATORY | Free + Student Pack | Step 1 | GitLab (no team familiarity gain), Bitbucket (weaker Actions ecosystem) |
| 2 | **GitHub Student Pack** | Unlocks Namecheap domain, DO credit, Sentry credit, Codespaces hours | Free money; the domain is strategically critical (Part C, Step 2) | MANDATORY | Free | Step 1 | none |
| 3 | **Namecheap domain** (via Pack) | Own domain: `app.` and `api.` subdomains on port 443 | Campus firewalls rarely block ordinary HTTPS to ordinary domains; this is our network-resilience strategy (ADR-001) | MANDATORY | Free 1 yr via Pack | Step 1 | Free subdomains like *.railway.app / *.vercel.app as PRIMARY (exactly the blockable class we are avoiding; Vercel kept as bonus only) |
| 4 | **DigitalOcean** | One droplet hosting API + PostgreSQL + Caddy via Docker Compose | Your preference + $200 Pack credit; full control; single failure domain we own | MANDATORY | Pack credit | Step 1-2 | AWS EC2/RDS (setup time tax, no benefit), Railway/Render (blockable domains, less control), GCP VM (credits better spent on Gemini) |
| 5 | **PostgreSQL 16 + pgvector** | Relational data + concept graph (adjacency) + vectors, one store | One connection string, one backup, one failure mode; recursive CTEs cover our graph needs | MANDATORY | Runs on droplet | Step 5-6 | Neo4j (second store for zero benefit at 45 nodes), managed PG as primary (third-party domain risk) |
| 6 | **Docker + Docker Compose** | Identical stack locally and on the droplet; one-command deploys | Parity kills "works on my machine"; rollback = previous image tag | MANDATORY | Free | Step 4 | Manual installs on droplet (config drift, un-rollbackable), Kubernetes (absurd overkill) |
| 7 | **Caddy** | Reverse proxy, automatic HTTPS, serves built frontend | TLS is literally zero-config (two lines per domain); nginx+certbot is an evening of yak-shaving | MANDATORY | Free | Step 6 | nginx+certbot (manual cert renewal wiring), Traefik (label-config learning curve) |
| 8 | **Google AI Studio (Gemini)** | Vision OCR (handwriting), embeddings, dialogue fallback | Best free-tier vision for handwritten math; generous quota; you hold GCP credits | MANDATORY | Free tier + credits | Step 1 | Tesseract (fails on pencil/ruled paper), MathPix (paid, quota risk) |
| 9 | **Anthropic API** (not Claude Pro) | Primary Socratic dialogue LLM | Strongest instruction-following for the strict Socratic contract | OPTIONAL-BUT-WANTED | Needs API credit (Claude Pro chat sub does NOT include API) | Step 1 (verify credit) | If no credit by Day 0: Gemini takes dialogue primary via one YAML edit; nothing else changes |
| 10 | **Groq Cloud** | Ultra-fast fallback text inference (Llama 3.3) | Latency insurance; free tier; third leg of the dialogue chain | MANDATORY (it's free resilience) | Free tier | Step 1 | Together/Fireworks (same role, no advantage over what you already have) |
| 11 | **Local upload storage (droplet)** | Doubt-photo storage in a dedicated Docker volume with a scheduled retention-cleanup job | Zero external dependency, zero extra accounts; 80 GB SSD is ample for demo scale; StorageProvider abstraction keeps S3/DO Spaces pluggable later via config only | MANDATORY | Included in droplet | Step 5-6 | AWS S3 (removed from MVP: setup complexity without practical benefit at this scale; remains the documented upgrade path), DO Spaces (same reasoning) |
| 12 | **Vercel** | PR preview deployments of the frontend; bonus CDN | Free preview-URL-per-PR is a genuine review accelerator for UI work | OPTIONAL | Free | Step 6 | Netlify (equivalent; Vercel's Vite integration is smoother). Demo day does NOT depend on it |
| 13 | **Sentry** | Error monitoring, both web and API | You will not watch logs at hour 30; Sentry pings you; Pack credit | MANDATORY | Pack credit / free tier | Step 6 | Self-hosted logging only (nobody reads logs during a hackathon), Datadog (overkill, paid) |
| 14 | **Neon (free)** |  Offsite restore target for nightly dumps | If the droplet dies, restore path exists | OPTIONAL (cheap insurance) | Free | Step 6 | Dump-files-only backups (a restorable live PG is faster to fail over to) |
| 15 | **Email service** | Transactional email | NOT NEEDED v1: students use class-code+PIN, teachers are seeded. `email.provider: none` | NOT NEEDED (config slot exists) | n/a | Never (roadmap: Resend) | Adding email now = auth scope creep |
| 16 | **WSL2 Ubuntu 24.04** | Linux dev environment inside Windows | See Part B analysis | MANDATORY (per Part B) | Free | Step 3 | Native Windows (Part B), full Linux dual-boot (disruptive, unnecessary) |
| 17 | **VS Code + WSL Remote ext** | Editor attached to the Linux environment | Safest, best-documented WSL integration | MANDATORY | Free | Step 3 | Antigravity IDE (fine as secondary; do not run two AI agents on one repo), Cursor (redundant with Claude Code) |
| 18 | **Claude Code** | The implementation agent for all coding sessions | Repo-aware, tool-using, honors CLAUDE.md; your chosen Sonnet workflow | MANDATORY | Your Claude sub/API | Step 3 | Copilot (autocomplete, not agentic), Cursor agent (second agent = conflicting edits) |
| 19 | **Node LTS (nvm) + pnpm** | Frontend toolchain | nvm pins versions across 4 machines; pnpm is fast + strict | MANDATORY | Free | Step 3 | System Node (version drift across teammates), npm/yarn (slower, looser) |
| 20 | **uv + Python 3.12** | Python toolchain and venvs | uv installs Python itself; lockfile discipline; 10-100x faster than pip | MANDATORY | Free | Step 3 | pip+venv (slow, no lockfile by default), conda (heavyweight) |
| 21 | **GitHub CLI (gh)** | Auth, PRs, secrets from terminal | Claude Code and scripts drive GitHub without browser round-trips | MANDATORY | Free | Step 3 | Browser-only workflow (breaks automation) |
| 22 | **Bruno** | API request collection, committed to repo | Offline-friendly, versioned with code | OPTIONAL | Free | Step 7 | Postman (cloud login, sync friction) |
| 23 | **OBS Studio** | Record the backup demo video | Non-negotiable demo insurance | MANDATORY | Free | Step 7 | Phone recording of screen (unwatchable on projector) |
| 24 | **n8n** | Workflow automation | Not in the product path (Bible Section 10); GitHub Actions cron covers ops chores | NOT NEEDED | n/a | Never | Its legitimate uses here are covered by tools already present |

---

# PART B - WSL2 + Docker vs Native Windows: the honest comparison

## The question, stated fairly
Everything in this stack technically RUNS on native Windows: Python, Node, Postgres installers, even Claude Code. So WSL is not mandatory in the "it will not work otherwise" sense. The question is which environment produces fewer surprises in 36 hours and at deploy time.

## Native Windows 11 workflow
**Advantages:** no virtualization layer to understand; slightly simpler mental model on day one; no dual-filesystem confusion; marginally less RAM used (no VM); everything in one place.
**Disadvantages, concretely:**
1. **Deployment asymmetry.** The droplet is Ubuntu. Native Windows dev means every path-separator assumption, line-ending (CRLF), file-permission bit, and shell-script incompatibility is discovered ON THE SERVER, at deploy time, which for us is continuously from Day 0. `deploy.sh`, `backup_db.sh`, Caddy configs, cron: all Linux artifacts you cannot rehearse natively.
2. **Docker Desktop on Windows uses WSL2 anyway.** This is the decisive technical fact: Docker Desktop's engine runs inside a WSL2 VM regardless. "Native Windows + Docker" is actually "WSL2 with extra steps and slower cross-OS file mounts." You do not escape WSL by avoiding it; you only escape understanding it.
3. **Toolchain friction tax.** Node native modules (node-gyp), Python wheels with C extensions, and CLI tools are all first-class on Linux and occasionally broken-on-Windows; each such incident costs 30-90 minutes you do not have.
4. **Claude Code and the entire tutorial-verse assume a POSIX shell.** Every command in our own Bible is bash.

## WSL2 workflow
**Advantages:** dev environment IS the production OS family (parity); Docker runs natively; all commands in all docs work verbatim; file watchers, symlinks, permissions behave like the droplet; performance excellent when files live in the Linux filesystem.
**Disadvantages, honestly:** one-time setup (~30-45 min); two filesystems to keep straight (the single real trap: keeping the repo under `/mnt/c/` destroys performance; keep it in `~/dev/`); occasional Windows-update-breaks-WSL-networking incidents (rare, rebootable); ~2-4 GB RAM for the VM (fine on a 16 GB machine, noticeable on 8 GB).

## Verdict
**Use WSL2. Not because it is common, but because Docker Desktop drags WSL2 in anyway, and the deploy target is Linux.** The choice is not "WSL vs no WSL"; it is "WSL you understand and work inside" vs "WSL hidden under Docker Desktop while you develop in a mismatched environment on top of it." The one scenario where native Windows would win: a machine with 8 GB RAM that cannot afford the VM, AND willingness to skip Docker locally (dev against remote services only). That trades demo-critical parity for comfort; rejected for this project.

**The two rules that prevent all common WSL pain:** (1) repo lives at `~/dev/studysetu`, never `/mnt/c/...`; (2) VS Code always opened via `code .` from inside WSL (bottom-left badge must say "WSL: Ubuntu-24.04").

---

# PART C - The Chronological Setup (Step 0 to Step 7)

## Step 0 - Freeze the decisions (30 min, together as a team)

**Plain language:** before touching any website, the team agrees on what is being built and where, so nobody creates a stray account "just in case." Random extra services are how secrets sprawl and bills appear.

**Do:**
1. Read README_BIBLE.md Sections 2-5 aloud as a team (20 min). These are the decisions; this step is ratification, not redesign.
2. Confirm the four externally-visible names now: GitHub repo name (`studysetu`), product name (freeze it now using docs/BRANDING.md), then 2-3 domain candidates matching it, demo class code (GJ8A).
3. Assign owners: INFRA (droplet, DNS, CI/CD: recommend Yash), CONTENT (taxonomy/items), UI (design tokens, Figma frames), API (auth/sync scaffold). One person creates ALL cloud accounts (the INFRA owner) so credentials have one home.

**Why now:** every later step references these names; renaming a repo, domain, or bucket later touches DNS, Caddy, CI, CORS, and configs simultaneously.

## Step 1 - Create every account and claim every credit (60-90 min, INFRA owner)

**Plain language:** one sitting, one checklist, one password manager. Claim free money first because some grants take time to activate.

**Do, in order:**
1. Password manager entry structure first (Bitwarden/1Password): one entry per service, with a `SETU/` folder. API keys will be pasted here BEFORE anywhere else.
2. **GitHub Student Pack**: verify/activate at education.github.com (can take hours to approve: hence first).
3. **Namecheap via Pack**: claim the free domain. Buy nothing extra.
4. **DigitalOcean via Pack**: claim credit ($200/1yr class). Do not create the droplet yet (Step 2).
5. **Google AI Studio** (aistudio.google.com): create API key. Note the current free-tier RPM/RPD limits for gemini-2.5-flash in the password manager entry (limits change; record what YOU see).
6. **Anthropic Console** (console.anthropic.com): check whether you have API credit (Claude Pro does NOT include API). If yes: create key. If no: decide now whether to buy $5-10 of credit (recommended for dialogue quality) or ship with Gemini-primary dialogue. Record the decision in docs/MEMORY.md.
7. **Groq Cloud**: create key.
9. **Sentry via Pack**: create org, two projects (`app-web`, `app-api`), copy both DSNs.
10. **Vercel**: sign in with GitHub (project link happens in Step 6). **Neon**: create the empty backup project.

**Why now:** account approvals and credit grants are the only steps with external latency; everything else is deterministic.

## Step 2 - Provision the cloud infrastructure (60 min, INFRA owner)

**Plain language:** rent the server, point your domain at it, lock its doors, and create the photo bucket. After this step your infrastructure exists and is secure, but empty.

**2a. Droplet:**
- Image: **Ubuntu 24.04 LTS x64**. Plan: **Basic, Regular SSD, 2 vCPU / 4 GB RAM** ($24/mo against credit; 2 GB is survivable but 4 GB gives Postgres + API + builds comfortable headroom). Region: **BLR1 (Bangalore)**: lowest latency to Vadodara. Enable **IPv4** (mandatory; it is how everyone reaches you). IPv6: enable (free, harmless). Monitoring agent: enable. Backups: enable (weekly, ~$4.80/mo of credit: cheap insurance).
- **Authentication: SSH key ONLY. Never password.** Generate in WSL later? No: generate NOW on Windows PowerShell if WSL not yet installed (`ssh-keygen -t ed25519`), or wait 15 minutes and do Step 3 first if you prefer one key from WSL. Either key works; the WSL key is the one you will use daily, so simplest order: do Step 3's WSL install first if doing Steps 2-3 same day, then return here. (Both orderings are fine; do not create password auth "temporarily.")

**2b. First-login hardening (SSH in as root once):**
```bash
adduser deploy && usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
# /etc/ssh/sshd_config: PasswordAuthentication no ; PermitRootLogin no
systemctl restart ssh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
apt update && apt upgrade -y && apt install -y fail2ban
# Docker (official convenience script is acceptable here):
curl -fsSL https://get.docker.com | sh && usermod -aG docker deploy
```
**Why:** password SSH on a public IP gets brute-forced within hours; ufw reduces the attack surface to exactly the three ports we serve; Docker installed now so Step 6's deploy has a target.

**2c. DNS (Namecheap dashboard):** A records `api` -> droplet IPv4, `app` -> droplet IPv4 (AAAA for IPv6 optional). TTL 5 min during the hackathon (fast changes if the droplet must be rebuilt).

**2d. Upload storage:** nothing to provision externally. Uploads live in the `uploads_data` Docker volume defined in `infra/docker-compose.yml`; retention is enforced by a scheduled cleanup task inside the API container (configurable via `storage.retention_hours` in config/app.yaml).

**Why now:** DNS propagation and droplet setup have latency and are prerequisites for CI/CD (Step 6); doing infra before code means the FIRST commit can deploy.

## Step 3 - Prepare the Windows 11 laptop (45 min per teammate, all four in parallel)

**Plain language:** install the Linux environment inside Windows, then the toolchain inside it. At the end, your laptop can run the same stack as the server.

**Do (PowerShell as Administrator):**
```powershell
wsl --install -d Ubuntu-24.04     # reboot when prompted, create Linux user
```
Install Docker Desktop for Windows; in Settings enable "Use WSL 2 based engine" and WSL integration for Ubuntu-24.04. Install VS Code + the "WSL" extension (and optionally Antigravity as a secondary editor: but only one AI agent edits the repo at a time).

**Inside the Ubuntu terminal:**
```bash
sudo apt update && sudo apt install -y git curl build-essential unzip
# Node via nvm + pnpm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc && nvm install --lts && corepack enable
# Python via uv
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
# GitHub CLI
sudo apt install -y gh
# Claude Code
npm i -g @anthropic-ai/claude-code
# Identity
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
ssh-keygen -t ed25519 -C "you@example.com"      # add ~/.ssh/id_ed25519.pub to GitHub AND to the droplet's deploy user
gh auth login
mkdir -p ~/dev
```
**Verification gate for this step:** `docker run hello-world` works inside Ubuntu; `node -v`, `uv --version`, `gh auth status`, `claude --version` all answer.

**Why now:** every subsequent step runs inside this environment; and doing it per-teammate in parallel today means nobody discovers a broken Docker install at hour 2 of the hackathon.

## Step 4 - Create the repository and lay down the skeleton (30 min, INFRA owner; others pull after)

**Plain language:** create the empty GitHub repo, clone it INTO LINUX, and copy in the Bible: the docs you already have become the first commit. The repo starts as documentation with empty scaffolding around it, which is exactly right: the rules exist before the code they govern.

```bash
gh repo create studysetu --private --clone --description "SETU: adaptive microlearning + AI doubt resolution"
cd ~/dev/studysetu
# Copy in the foundation: README_BIBLE.md, CLAUDE.md, docs/, config/app.example.yaml, .env.example
mkdir -p apps/web apps/api packages/shared content prompts infra scripts e2e .github/workflows docs/adr
cp config/app.example.yaml config/app.yaml
printf ".env\nnode_modules/\n__pycache__/\n.venv/\ndist/\n*.local\n" > .gitignore
git add -A && git commit -m "chore: engineering foundation (Bible v1.0)" && git push
```
On GitHub: Settings -> Branches -> protect `main` (require PR + status checks). Add teammates as collaborators.

**Why now:** branch protection and the docs-first commit establish the workflow BEFORE the first feature; retrofitting discipline never happens at hour 20.

## Step 5 - First Claude Code session: generate the boilerplate (60-90 min)

**Plain language:** open Claude Code inside the repo and have it build the empty-but-running skeleton: a hello-world API, a hello-world PWA, the compose files, and CI configs. No features. The goal is a stack that boots, not a product.

```bash
cd ~/dev/studysetu && claude
```
Then use PROMPTS.md P1 with this task (paste as-is):
> Read CLAUDE.md, docs/ARCHITECTURE.md, docs/RULES.md, docs/PHASES.md Phase 0. Task: scaffold the monorepo per README_BIBLE.md Section 6. apps/api: FastAPI app factory, /healthz, app/config.py loading config/app.yaml + .env via pydantic-settings, Alembic initialized, Dockerfile. apps/web: Vite React TS PWA via vite-plugin-pwa, src/lib/config.ts fetching /config.json, Tailwind + tokens from CSS vars, Dockerfile-less (static build). infra/: docker-compose.yml (api, postgres:16 with pgvector, caddy) + docker-compose.dev.yml + Caddyfile for app.<domain>/api.<domain>. .github/workflows/ci.yml (web lint/typecheck/test, api ruff/pytest) and deploy.yml (build+push GHCR, SSH deploy, migrate, healthcheck, rollback). scripts/seed_demo.py stub. Propose the plan first; no features, only skeleton.

Review the plan, approve, let it build, then locally:
```bash
docker compose -f infra/docker-compose.dev.yml up --build
# expect: http://localhost:8000/healthz -> {"ok": true}, web dev server serves the shell
```
Commit via PR (yes, even this: the PR exercises CI for the first time).

**Why now and not during the hackathon:** scaffolding is zero-creativity, high-friction work: exactly what you do NOT want competing with judged features for hackathon hours. (Most hackathons permit pre-built boilerplate; verify TetraTHON's rule, and keep this commit clearly labeled `chore: scaffold` with no product features, plus a 10-minute re-scaffold path via this step if a clean start is required.)

## Step 6 - Wire secrets, CI/CD, and the first real deployment (60 min)

**Plain language:** teach GitHub how to reach your droplet, give both environments their secrets, and watch a merge to main appear on your real domain. This is the moment continuous deployment becomes real.

**Do:**
1. Droplet: as `deploy`, `mkdir ~/app && nano ~/app/.env` (paste production values from the password manager: DATABASE_URL with a strong password, JWT_SECRET via `openssl rand -hex 32`, all AI keys, Sentry DSNs).
2. GitHub repo -> Settings -> Secrets and variables -> Actions: `DROPLET_HOST`, `DROPLET_USER=deploy`, `DROPLET_SSH_KEY` (a NEW dedicated deploy keypair: `ssh-keygen -t ed25519 -f deploy_key`; public half appended to the droplet's `~/.ssh/authorized_keys`, private half pasted as the secret), plus `GHCR` uses the built-in `GITHUB_TOKEN`.
3. Merge a trivial PR to main. Watch Actions: build -> push image -> SSH -> `docker compose pull && up -d` -> alembic upgrade -> curl /healthz.
4. Verify in a browser: `https://api.<domain>/healthz` (Caddy should have provisioned TLS automatically on first request) and `https://app.<domain>` shows the shell.
5. Vercel (optional bonus): import the repo, root `apps/web`: preview URLs now appear on every PR.
6. Sentry: trigger one test error each side; confirm both projects receive it.
7. Backups: on the droplet, a root cron `pg_dump | gzip` nightly into the `backups_data` volume, `scp`-pulled weekly to a teammate laptop, plus a weekly restore-test into Neon (insurance is only real if restored once). DO droplet weekly snapshots stay enabled as the outer layer.

**Why now:** from this moment, every merged feature is live within minutes for the whole team and for rehearsals: the entire "deploy continuously from the beginning" philosophy depends on this step preceding feature #1.

## Step 7 - Full verification gate (45 min, whole team)

**Plain language:** a cold, honest rehearsal of the foundation. Each teammate proves their machine works; the INFRA owner proves the pipeline works; the team proves the fallback plans exist. Nothing here should be new: this step only confirms.

**The gate checklist (all must pass):**
- [ ] Each teammate: clone fresh, `docker compose -f infra/docker-compose.dev.yml up` boots, web + api reachable locally
- [ ] Each teammate: a one-line PR passes CI and gets a Vercel preview
- [ ] Merge to main -> live on `api.<domain>` in under 5 minutes (timed)
- [ ] `ai_smoke.py` (Claude Code writes it in Step 5): calls ai.generate through the chain; then temporarily poison the primary key in droplet .env -> chain fails over -> restore key. Failover is now a TESTED fact, not a hope.
- [ ] Postgres: `docker exec` into the container, `CREATE EXTENSION IF NOT EXISTS vector;` confirmed in migrations
- [ ] Uploads: a test photo POSTed to the API lands in the `uploads_data` volume; the cleanup task removes files older than the configured retention (test with retention temporarily set to 1 minute)
- [ ] Sentry shows both test events; DO monitoring graphs visible
- [ ] Phone hotspot: teacher-laptop reaches `api.<domain>` through it (the venue-network fallback, rehearsed once)
- [ ] Backup exists in the backups volume; one restore into Neon completed
- [ ] Password manager holds every credential; `.env` files exist ONLY on the droplet and in each dev's local repo (never in git: verify with `git log -p | grep -i api_key` returning nothing)
- [ ] docs/MEMORY.md entry written: "Foundation verified" with date and any deviations

**When every box is ticked, this document retires and docs/PHASES.md Phase 1 begins.**

---

## Appendix: time budget and ordering summary
Step 0 (30m, team) -> Step 1 (90m, INFRA) -> Step 3 (45m, ALL, parallel with Step 1-2) -> Step 2 (60m, INFRA) -> Step 4 (30m) -> Step 5 (90m) -> Step 6 (60m) -> Step 7 (45m, team). Total: roughly one focused day for the INFRA owner, under two hours for everyone else. Steps 2 and 3 can swap or interleave; everything else is strictly ordered.
