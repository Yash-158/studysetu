# INFRA_SETUP_GUIDE.md - Zero-to-Ready Onboarding Manual (v2)
From an empty Windows 11 laptop to a fully configured development environment and cloud infrastructure. Every step follows the same five-part structure: Objective, Why required, Can I customize, Implementation, Common mistakes. Follow top to bottom; do not skip verification lines.

> **Amendment (M0 domain integration, current):** this droplet (64.227.177.181) now hosts multiple team projects behind ONE shared Caddy layer living in the separate `caffeineclause-edge` repo, not inside this project's compose (docs/ARCHITECTURE.md ADR-011). Domain is claimed: `caffeineclause.tech`, flat subdomains `studysetu.` (frontend) / `studysetu-api.` (backend). Deploy path is `/home/deploy/studysetu`, not `~/app`. Sections 8-9 below (droplet provisioning, domain/DNS) are retained as the general playbook for provisioning a NEW droplet or domain from scratch; for THIS droplet, docs/DEPLOYMENT.md + infra/droplet-bootstrap.sh are the current source of truth.

## THE NAMING RULE (read before anything else)
Infrastructure names are GENERIC and permanent; the product name is branding and lives ONLY in `config/app.yaml`, UI copy, and docs. This means renaming the product later touches one YAML block, zero cloud resources. Fixed infrastructure names used throughout this guide:

| Thing | Name | Customizable? |
|---|---|---|
| GitHub repo / workspace folder | `studysetu` | Yes, but pick ONCE, before Section 4 |
| Droplet hostname | `prod-1` | Yes (cosmetic) |
| Cloud firewall | `prod-fw` | Yes (cosmetic) |
| Server user | `deploy` | Yes, but every doc assumes `deploy`; keep it |
| Upload storage | Docker volume `uploads_data` on the droplet (no external service in MVP) | Dir/retention via config/app.yaml |
| Sentry projects | `app-web`, `app-api` | Cosmetic |
| Database / DB user | `appdb` / `app` | Keep as written (matches compose + .env.example) |
| Env override prefix | `APP__` | FIXED (code depends on it) |
| Docker services | `api`, `postgres`, `caddy` | FIXED (compose + CI depend on them) |
| Bitwarden folder | `PROJECT` | Cosmetic |
| Domain | user-facing: choose AFTER the product name is frozen (docs/BRANDING.md) | Yours |

## MASTER CHECKLIST (print; tick as you go)
Accounts: [ ] Bitwarden [ ] GitHub+2FA [ ] Student Pack approved [ ] Namecheap+domain [ ] DigitalOcean+credit [ ] Google AI Studio [ ] Groq [ ] Anthropic (or recorded skip) [ ] Sentry [ ] Vercel [ ] Neon
Resources: [ ] WSL2+toolchain on every laptop [ ] workspace `~/dev/studysetu` with full folder skeleton [ ] Droplet prod-1 hardened [ ] prod-fw attached [ ] DNS api./app. records [ ] uploads/backups Docker volumes (declared at scaffold time)
Credentials in Bitwarden `PROJECT` folder: [ ] laptop SSH pub key [ ] droplet IP [ ] deploy user password [ ] GH-Actions deploy private key [ ] Gemini key [ ] Groq key [ ] Anthropic key/decision [ ] Sentry DSN x2 [ ] Neon string [ ] JWT secret [ ] DB password
Verified: [ ] ssh deploy works, root refused [ ] docker hello-world on laptop AND droplet [ ] DNS resolves [ ] 3x AI curl tests [ ] nothing sensitive outside Bitwarden

---

# SECTION 1 - Password manager

**Objective:** one secure home for every secret created in this guide.
**Why required:** you are about to generate ~12 credentials across 10 platforms; several are shown exactly once. Scattering them across Notepad, WhatsApp, and screenshots is how teams lose demo day to a lockout, and how keys leak.
**Can I customize:** any manager works (1Password, KeePassXC); steps assume Bitwarden (free, syncs to phone). Folder name `PROJECT` is cosmetic.
**Implementation:**
1. Browser -> `https://bitwarden.com` -> Get Started -> create account. The master password is the ONE password not stored digitally: write it on paper, keep at home.
2. Install the Bitwarden browser extension (it will prompt) and the phone app.
3. In the web vault: New -> Folder -> `PROJECT`.
4. Standing rule for this entire guide: the instant any key/secret appears on screen, create an item `<Service> - <what>` in `PROJECT` and paste it, BEFORE doing anything else with it.
**Verify:** extension unlocks; folder exists.
**Common mistakes:** weak master password; skipping the phone app (you will want TOTP codes there); "I'll save it after this step" (shown-once keys die this way).

# SECTION 2 - WSL2, Docker Desktop, VS Code, toolchain (every teammate)

**Objective:** a Linux development environment inside Windows that matches the production server, plus the compilers/runtimes the project needs.
**Why required:** the server is Ubuntu; developing on Ubuntu-in-Windows means scripts, paths, permissions, and Docker behave identically in dev and prod. Decisive fact: Docker Desktop runs inside WSL2 anyway, so avoiding WSL only hides it (full analysis: SETUP_STEPS.md Part B). Node/pnpm drive the frontend; uv/Python drive the API; gh drives GitHub automation; Claude Code is the implementation agent.
**Can I customize:** Ubuntu 24.04 is the pinned version (matches droplet): keep it. Your Linux username is yours. Editor: VS Code assumed; Antigravity acceptable as secondary, but only ONE AI agent edits the repo at a time.
**Implementation:**
1. PowerShell AS ADMINISTRATOR (Start -> type PowerShell -> right-click -> Run as administrator):
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
   Reboot when prompted. On first launch a terminal asks for a Linux username (lowercase, e.g. `yash`) and password (store: `PROJECT/WSL - sudo password`).
2. Install Docker Desktop for Windows (docker.com -> Download). Open it -> Settings -> General: "Use the WSL 2 based engine" ticked -> Resources -> WSL Integration: toggle ON for Ubuntu-24.04 -> Apply.
3. Install VS Code (code.visualstudio.com) -> open -> Extensions (Ctrl+Shift+X) -> install "WSL" (by Microsoft).
4. Open the Ubuntu terminal (Start -> Ubuntu 24.04). EVERY Linux command in this guide runs here unless stated otherwise. Run block by block:
   ```bash
   sudo apt update && sudo apt install -y git curl build-essential unzip gh
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   source ~/.bashrc && nvm install --lts && corepack enable
   curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
   npm i -g @anthropic-ai/claude-code
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ssh-keygen -t ed25519 -C "yourname-laptop"    # Enter x3 (default path, no passphrase is acceptable for hackathon)
   cat ~/.ssh/id_ed25519.pub                      # copy this line -> Bitwarden "SSH - laptop public key"
   ```
**Verify:** `docker run hello-world` prints a success message inside Ubuntu; `node -v`, `uv --version`, `gh --version`, `claude --version` all answer.
**Common mistakes:** running Linux commands in PowerShell (prompt must show `user@machine:~$`, not `PS C:\>`); forgetting WSL Integration toggle in Docker Desktop (docker "command not found" in Ubuntu); virtualization disabled in BIOS (WSL install error: enable SVM/VT-x in BIOS).

# SECTION 3 - The project workspace and folder skeleton

**Objective:** create the folder where the project lives, in the right filesystem, with the complete top-level structure and a purpose for every folder.
**Why required:** WSL has two filesystems: Linux-native (`~/...`) and the mounted Windows drive (`/mnt/c/...`). Code MUST live Linux-native: cross-OS file access is 5-10x slower and breaks file watchers (Vite hot reload, Docker mounts). Creating the skeleton first means every later tool (Claude Code, CI, compose) finds the structure it expects.
**Can I customize:** parent folder `~/dev` is convention (change if you like); repo folder name must match the GitHub repo name chosen in Section 4 (`studysetu` assumed everywhere).
**Implementation (Ubuntu terminal):**
```bash
mkdir -p ~/dev/studysetu && cd ~/dev/studysetu
mkdir -p apps/web apps/api packages/shared content prompts infra scripts e2e docs/adr .github/workflows config
```
Folder purposes (never put anything else in them):
- `apps/web` frontend PWA only. Never: API keys, server code.
- `apps/api` backend only. Never: UI assets. Provider SDKs only inside `apps/api/app/ai/`.
- `packages/shared` cross-language contracts (generated API types, BKT test vectors). Never: hand-written app logic.
- `content` curriculum data (taxonomy, items, lessons). Never: code.
- `prompts` versioned LLM prompt files. Never: prompts pasted inline in code.
- `infra` docker-compose files, Caddyfile, deploy script. Never: secrets.
- `scripts` operational one-offs (seed, embed, backup). `e2e` Playwright specs. `docs` the Bible chapters; `docs/adr` decision records. `.github/workflows` CI/CD. `config` app.yaml (non-secret config only).
- Open the workspace correctly, ALWAYS from inside Ubuntu: `code .` (first run installs the VS Code server; the window's bottom-left badge must read "WSL: Ubuntu-24.04").
**Verify:** `ls` shows all folders; VS Code badge says WSL.
**Common mistakes:** cloning/creating under `/mnt/c/Users/...` (the single most damaging WSL mistake); opening the folder from Windows Explorer instead of `code .` (silently edits via the slow path).

# SECTION 4 - GitHub + Student Developer Pack

**Objective:** the account that hosts code, runs CI/CD, stores container images, and unlocks free credits (domain, DO, Sentry).
**Why required:** GitHub is the project's backbone: repo, Actions (CI/CD), GHCR (Docker images), secrets store. The Student Pack funds the domain and droplet. Depends on it: literally everything downstream. Mandatory. Replaceable later: painfully (GitLab), so choose correctly now. Skipping it: no project.
**Can I customize:** username is yours (it appears in the judged repo URL: keep it professional). Repo name `studysetu`: changeable, but decide NOW and use consistently.
**Implementation:**
1. `https://github.com` -> Sign up -> verify email.
2. 2FA immediately: avatar (top-right) -> Settings -> Password and authentication -> Two-factor authentication -> Enable -> Authenticator app -> scan with Bitwarden/phone. Download recovery codes -> paste contents into Bitwarden (`GitHub - 2FA recovery codes`) -> delete the downloaded file.
3. SSH key: Settings -> SSH and GPG keys -> New SSH key -> Title `laptop`, Type: Authentication Key -> paste the public key from Section 2 -> Add.
4. In Ubuntu: `gh auth login` -> GitHub.com -> SSH -> pick your key -> Login with web browser -> follow the code.
5. Student Pack: `https://education.github.com/pack` -> Sign up for Student Developer Pack -> select GLS University, verify with university email or student ID photo -> Submit. Approval: minutes to days. THIS WAIT IS WHY SECTION 4 IS EARLY: continue Sections 5-8 while waiting; Sections 9 (domain) and 10.1 (DO credit) need approval.
6. Create the repo (Ubuntu, inside the workspace):
   ```bash
   cd ~/dev/studysetu
   git init -b main
   gh repo create studysetu --private --source=. --remote=origin
   printf ".env\nnode_modules/\n__pycache__/\n.venv/\ndist/\n*.local\n" > .gitignore
   git add -A && git commit -m "chore: workspace skeleton" && git push -u origin main
   ```
7. Branch protection: repo page on github.com -> Settings -> Branches -> Add branch ruleset (or classic protection rule) -> target `main` -> require pull request before merging + require status checks -> save. Add teammates: Settings -> Collaborators.
**Verify:** `ssh -T git@github.com` greets you by username; repo visible online; education page shows Pack active (after approval).
**Common mistakes:** skipping 2FA recovery codes (account loss = repo loss mid-hackathon); creating the repo via the website and cloning to `/mnt/c` (Section 3 violation); waiting idle for Pack approval instead of continuing.

# SECTION 5 - Google AI Studio (Gemini API)

**Objective:** the API key powering vision OCR (handwriting), embeddings, and the dialogue fallback.
**Why required:** the doubt pipeline's photo extraction depends on a vision model; Gemini Flash is the strongest free-tier option for handwritten Indian-classroom math. Depends on it: `apps/api/app/ai/providers/gemini.py`, embeddings for concept matching. Mandatory. Replaceable: yes, per the provider-chain config (that is the whole point of the AI gateway).
**Can I customize:** nothing meaningful; one key is one key. Model IDs live in `config/app.yaml`, not here.
**Implementation:**
1. `https://aistudio.google.com` -> sign in with Google -> accept terms.
2. Get API key (sidebar or top-right) -> Create API key -> "Create API key in new project" if asked (auto-creates a GCP project; you never need the GCP console for this project). Copy -> Bitwarden (`Gemini - API key`).
3. On the same page, note the free-tier rate limits displayed for the flash model into the Bitwarden item notes (record what YOU see; limits change).
**Verify (Ubuntu):** `curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY" | head -c 300` -> JSON listing models.
**Common mistakes:** confusing AI Studio keys with GCP service-account JSON (you need only the AI Studio key: no JSON file downloads); leaking the key by testing it in random online tools.

# SECTION 6 - Groq

**Objective:** API key for ultra-fast fallback text generation.
**Why required:** third leg of the dialogue provider chain; if Claude and Gemini both stall during judging, Groq's Llama endpoint answers in under a second. It is free resilience. Depends on it: `providers/groq.py`. Mandatory (because free). Replaceable: trivially, via config.
**Can I customize:** nothing.
**Implementation:** `https://console.groq.com` -> sign in with GitHub -> API Keys -> Create API Key -> name `app` -> copy -> Bitwarden (`Groq - API key`).
**Verify:** `curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer YOUR_KEY" | head -c 300` -> JSON model list.
**Common mistakes:** none of substance; five-minute section.

# SECTION 7 - Anthropic API (decision point)

**Objective:** decide, then optionally create, the key for the primary Socratic dialogue model.
**Why required:** Claude Sonnet follows the strict Socratic output contract (never reveal the answer before two attempts, structured steps) most reliably. Depends on it: dialogue quality only: the system runs fully on Gemini if skipped. OPTIONAL-BUT-RECOMMENDED. Critical fact: your Claude Pro chat subscription does NOT include API access; API needs separate credit.
**Can I customize:** the whole decision. Option A: add $5-10 API credit (recommended). Option B: skip; in `config/app.yaml` move `gemini_flash` to the front of `ai.chains.dialogue`. Either way, record the decision in `docs/MEMORY.md` today.
**Implementation (Option A):** `https://console.anthropic.com` -> sign up -> Billing -> add credit -> API Keys -> Create Key -> name `app` -> copy -> Bitwarden (`Anthropic - API key`).
**Verify:** 
```bash
curl -s https://api.anthropic.com/v1/messages -H "x-api-key: YOUR_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-sonnet-4-6","max_tokens":10,"messages":[{"role":"user","content":"say ok"}]}'
```
JSON containing "ok" = working; a credit-related error = revisit the decision.
**Common mistakes:** assuming Pro covers the API (the #1 confusion); deferring the decision (it silently becomes "skipped" and nobody re-orders the chain: record it NOW).

# SECTION 8 - DigitalOcean: the production server

**Objective:** one hardened Ubuntu server (droplet `prod-1`) that will run the entire backend stack via Docker.
**Why required:** ADR-001: everything the demo needs lives on one server you control, reached via your own domain over plain HTTPS: the posture campus firewalls do not block. Depends on it: API, database, Caddy, deployments. Mandatory. Replaceable: any VPS vendor (Hetzner, Lightsail) with zero code changes: it is just a Linux box, which is exactly why we chose this shape.
**Can I customize:** Region: BLR1 recommended (closest to Vadodara); any nearby region works. Size: 2 vCPU/4 GB recommended; 2 GB survives but swaps under builds. Hostname/firewall names cosmetic. NOT customizable: Ubuntu 24.04, SSH-key-only auth, the hardening block, ports 22/80/443 only.
**Implementation:**
1. Student Pack page -> DigitalOcean offer -> Get access (link carries the credit) -> sign up (GitHub sign-in fine) -> add card (required; credit is spent first) -> Manage -> Billing: confirm promo credit; set a Billing alert at $5. Enable 2FA (My Account -> Security).
2. Create -> Droplets: Region **Bangalore BLR1** | Image: OS -> Ubuntu **24.04 (LTS) x64** | Type **Basic**, CPU **Regular SSD**, plan **2 vCPU / 4 GB / 80 GB** | **Enable Backups** (weekly) | Advanced: enable **IPv6**, enable **Monitoring** | Authentication: **SSH Key** -> New SSH Key -> paste your laptop public key -> name `laptop` | Hostname `prod-1` | Create.
3. Copy the IPv4 address -> Bitwarden (`Droplet - IP`).
4. Firewall BEFORE first login: Networking -> Firewalls -> Create: name `prod-fw`; Inbound: SSH TCP 22 (All IPv4+IPv6), HTTP TCP 80, HTTPS TCP 443, NOTHING else (no 5432, no 8000: Postgres is never exposed); Outbound: defaults. Apply to droplet `prod-1` -> Create.
5. Harden (Ubuntu terminal): `ssh root@DROPLET_IP` (type yes), then run the blocks:
   ```bash
   adduser deploy            # strong password -> Bitwarden "Droplet - deploy password"
   usermod -aG sudo deploy
   rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
   sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
   sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
   systemctl restart ssh
   ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
   apt update && apt upgrade -y && apt install -y fail2ban unattended-upgrades
   systemctl enable --now fail2ban
   curl -fsSL https://get.docker.com | sh && usermod -aG docker deploy
   timedatectl set-timezone Asia/Kolkata
   exit
   ```
6. Deploy keypair for GitHub Actions: `ssh deploy@DROPLET_IP`, then:
   ```bash
   ssh-keygen -t ed25519 -f ~/deploy_key -C "gh-actions" -N ""
   cat ~/deploy_key.pub >> ~/.ssh/authorized_keys
   cat ~/deploy_key      # entire output -> Bitwarden "GH Actions - deploy private key"
   rm ~/deploy_key && mkdir -p ~/app && exit
   ```
   (`~/app` is where the production `.env` and compose files will live.)
**Verify:** `ssh deploy@DROPLET_IP` works; `ssh root@DROPLET_IP` says Permission denied; on the droplet `docker run hello-world` (log out/in once first) and `sudo ufw status` shows exactly 22/80/443.
**Common mistakes:** choosing Password authentication "just for now" (brute-forced within hours); testing root lockout in the SAME terminal that is already logged in (open a new one); forgetting `rm ~/deploy_key` (private keys never rest on servers); exposing 5432 "to connect DBeaver" (tunnel over SSH instead: `ssh -L 5432:localhost:5432 deploy@IP`).

# SECTION 9 - Domain (Namecheap via Student Pack) + DNS

**Objective:** your own domain, with `api.` and `app.` subdomains pointing at the droplet.
**Why required:** the network-resilience strategy (ADR-001): campus firewalls rarely block ordinary HTTPS to an ordinary custom domain, and Caddy will mint free TLS certificates for it automatically. Depends on it: Caddy config, CORS origins, everything user-facing. Mandatory. Replaceable: any registrar; DNS records are portable.
**Can I customize:** the domain IS the customization, and it is user-facing branding. RULE: freeze the product name (docs/BRANDING.md) BEFORE claiming the domain: the Pack gives you ONE free domain. If the team cannot decide yet, claim a neutral domain and plan to buy the branded one later ($10-ish), pointing both at the same droplet.
**Implementation:**
1. Student Pack page -> Namecheap offer -> Get access -> connect GitHub -> search your chosen name (`.me` is the Pack's free TLD; verify on the offer page) -> add to cart -> checkout shows $0.00 with the education promo -> create the Namecheap account during checkout -> complete.
2. Enable 2FA: Profile -> Security.
3. DNS: Domain List -> Manage -> **Advanced DNS** -> Host Records: delete any default parking/URL-redirect records, then Add New Record twice:
   - Type **A Record** | Host `api` | Value = DROPLET_IP | TTL 5 min
   - Type **A Record** | Host `app` | Value = DROPLET_IP | TTL 5 min
**Verify (Ubuntu, allow 5-30 min):** `nslookup api.YOURDOMAIN.me` and `nslookup app.YOURDOMAIN.me` both return the droplet IP.
**Common mistakes:** claiming the free domain before the name is frozen (wasted claim); leaving Namecheap's parking CNAME in place (hijacks your root domain); setting long TTLs (slow to fix if the droplet is rebuilt).

# SECTION 10 - Upload storage (nothing to set up: read and move on)

**Objective:** understand where uploaded notebook photos live: no external service required.
**Why:** MVP stores uploads on the droplet in a dedicated Docker volume (`uploads_data`), registered in the database's `uploads` table, behind a StorageProvider abstraction with a scheduled retention-cleanup task (default: delete after 1 hour). External object storage (AWS S3 / DO Spaces) was removed from the MVP (ADR-006): at hackathon scale it added an entire cloud account, IAM, CORS, and lifecycle configuration for no practical benefit against 80 GB of local SSD.
**Can I customize:** `storage.upload_dir`, `storage.retention_hours`, `storage.cleanup_interval_minutes`, `storage.max_upload_mb` in config/app.yaml. Switching to S3/Spaces later = implementing nothing: set `storage.provider: s3` and fill the commented .env keys (the S3StorageProvider ships as part of the abstraction when needed).
**Implementation:** none now. The `uploads_data` and `backups_data` volumes are declared in `infra/docker-compose.yml` during scaffolding (SETUP_STEPS.md Step 5).
**Verify:** deferred to SETUP_STEPS.md Step 7 (test upload lands in the volume; cleanup task removes an expired file).
**Common mistakes:** provisioning S3 anyway "to be safe" (unused credentials are pure attack surface); pointing upload_dir outside the volume (files then die with the container).

# SECTION 11 - Sentry

**Objective:** two error-monitoring projects (`app-web`, `app-api`) that email you when anything breaks.
**Why required:** at hour 30 nobody is watching logs; Sentry watches for you, with stack traces. Depends on it: nothing structurally: it observes. Mandatory (it is free and demo-saving). Replaceable: yes (GlitchTip, or nothing).
**Can I customize:** org and project names cosmetic (keep `app-web`/`app-api` to match .env.example).
**Implementation:** Student Pack -> Sentry offer (or sentry.io -> sign up with GitHub) -> create org -> Projects -> Create Project -> platform **React**, name `app-web` -> copy the DSN from the setup snippet -> Bitwarden (`Sentry - web DSN`). Repeat with platform **FastAPI/Python**, name `app-api` -> Bitwarden (`Sentry - api DSN`). Enable 2FA in settings.
**Verify:** both projects listed, showing "Waiting for events" (real test events fire during SETUP_STEPS.md Step 6).
**Common mistakes:** one shared project for web+api (noise makes it useless); ignoring the DSNs now and hunting for them later.

# SECTION 12 - Vercel (optional)

**Objective:** automatic preview deployments of the frontend on every PR.
**Why required:** design review velocity: every UI PR gets a URL anyone can open on a phone. The DEMO does not depend on Vercel (Caddy serves the frontend from the droplet); this is a convenience layer. Optional. Skipping it: you review UI via local dev servers only.
**Can I customize:** everything; it is detachable by design.
**Implementation:** `https://vercel.com` -> Continue with GitHub -> Hobby plan. STOP here for now; import later (after the scaffold exists): Add New -> Project -> `studysetu` -> **Root Directory: `apps/web`** -> Framework: Vite -> Deploy.
**Verify:** account dashboard loads.
**Common mistakes:** importing with root directory unset (build fails at repo root); treating the vercel.app URL as the demo URL (it is the blockable-domain class we architected away from).

# SECTION 13 - Neon (optional backup target)

**Objective:** a free offsite Postgres that nightly dumps restore into, so a dead droplet is a 15-minute recovery, not a catastrophe.
**Why required:** self-hosting the DB (ADR-001) means we own disaster recovery. Optional but cheap insurance. Skipping it: local dump files + DO snapshots remain your restore path (slower).
**Implementation:** `https://neon.tech` -> sign up with GitHub -> Create project `backup`, Postgres 16, an Asia region -> copy connection string -> Bitwarden (`Neon - backup connection string`).
**Verify:** dashboard shows the database active.
**Common mistakes:** pointing the APP at Neon (it is a backup target only: the app's DATABASE_URL points at the droplet's own Postgres).

# SECTION 14 - Generate application secrets

**Objective:** the JWT signing secret and database password, generated properly, stored once.
**Why required:** these two secrets gate all auth and all data; they must be random, and they must exist before the droplet's `.env` is written in SETUP_STEPS.md Step 6.
**Implementation (Ubuntu):**
```bash
openssl rand -hex 32     # -> Bitwarden "APP - JWT secret"
openssl rand -hex 16     # -> Bitwarden "APP - DB password" (hex avoids URL-breaking characters)
```
**Common mistakes:** inventing passwords by hand; using characters like @ : / % in the DB password (they break connection URLs).

# SECTION 15 - FINAL VERIFICATION SWEEP

Every line must be true before development begins. Then return to SETUP_STEPS.md Step 4 onward (repo Bible commit, scaffold, CI/CD wiring, first deploy).
- [ ] Every teammate: Section 2 verifications pass on their laptop
- [ ] Workspace exists Linux-native with the full skeleton; VS Code opens via `code .` showing WSL badge
- [ ] GitHub: 2FA + recovery codes stored; repo `studysetu` pushed; branch protection on
- [ ] `ssh deploy@IP` works; root refused; droplet docker hello-world; ufw = 22/80/443
- [ ] DNS: both subdomains resolve to the droplet
- [ ] Gemini, Groq, (Anthropic) curl tests pass; Anthropic decision in MEMORY.md
- [ ] Sentry: two projects, two DSNs stored
- [ ] Vercel + Neon accounts live (or consciously skipped, noted in MEMORY.md)
- [ ] JWT secret + DB password generated and stored
- [ ] Bitwarden `PROJECT` folder audit: 12+ items present; nothing sensitive in Downloads/Desktop/chat apps
