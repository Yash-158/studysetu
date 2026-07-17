#!/usr/bin/env bash
# Run inside WSL from the repo root: bash scripts/verify_local.sh
set -uo pipefail
PASS=0; FAIL=0; WARN=0
ok(){ printf "  \e[32m[PASS]\e[0m %s\n" "$1"; PASS=$((PASS+1)); }
bad(){ printf "  \e[31m[FAIL]\e[0m %s -- %s\n" "$1" "$2"; FAIL=$((FAIL+1)); }
warn(){ printf "  \e[33m[WARN]\e[0m %s -- %s\n" "$1" "$2"; WARN=$((WARN+1)); }
hdr(){ printf "\n\e[1m%s\e[0m\n" "$1"; }

hdr "1. Environment"
grep -qiE "microsoft|wsl" /proc/version 2>/dev/null && ok "WSL detected" || warn "WSL" "native Linux ok; native Windows is not"
case "$PWD" in /mnt/*) bad "Repo location" "under /mnt/* - move to ~/dev/studysetu";; *) ok "Linux-native filesystem";; esac

hdr "2. Toolchain"
c(){ command -v "$1" >/dev/null 2>&1 && ok "$2 ($($3 2>/dev/null|head -1))" || bad "$2" "$4"; }
c git "Git" "git --version" "apt install git"
c docker "Docker" "docker --version" "Docker Desktop + WSL integration"
docker compose version >/dev/null 2>&1 && ok "Docker Compose" || bad "Compose" "plugin missing"
c node "Node" "node -v" "nvm install --lts"
c pnpm "pnpm" "pnpm -v" "corepack enable"
c uv "uv" "uv --version" "astral.sh/uv installer"
c python3 "Python" "python3 -V" "uv manages pythons"
c claude "Claude Code" "claude --version" "npm i -g @anthropic-ai/claude-code"
c gh "GitHub CLI" "gh --version" "apt install gh"
gh auth status >/dev/null 2>&1 && ok "gh authenticated" || bad "gh auth" "gh auth login"

hdr "3. Repository"
for d in apps/web apps/api config db/migrations infra scripts docs prompts e2e .github/workflows; do
  [ -d "$d" ] && ok "dir $d" || bad "dir $d" "missing"; done
for f in README.md CLAUDE.md docs/MEMORY.md docs/RULES.md docs/ROADMAP.md config/app.yaml infra/docker-compose.dev.yml; do
  [ -f "$f" ] && ok "file $f" || bad "file $f" "missing"; done
[ -f .env ] && ok ".env present" || warn ".env" "cp .env.example .env"
grep -q "^\.env$" .gitignore 2>/dev/null && ok ".env git-ignored" || bad ".gitignore" ".env not ignored"
if [ -f .env ]; then grep -q "^JWT_SECRET=..\+" .env && ok "JWT_SECRET set" || warn "JWT_SECRET" "empty"; fi

hdr "4. Stack"
docker info >/dev/null 2>&1 && ok "Docker daemon" || bad "Docker daemon" "Desktop running? WSL integration?"
if docker compose -f infra/docker-compose.dev.yml ps --format '{{.Service}}' 2>/dev/null | grep -q postgres; then
  docker compose -f infra/docker-compose.dev.yml exec -T postgres pg_isready -U app >/dev/null 2>&1 \
    && ok "Postgres up + ready" || bad "Postgres" "container up, not ready"
  N=$(docker compose -f infra/docker-compose.dev.yml exec -T postgres psql -U app -d appdb -tAc "SELECT count(*) FROM schema_migrations" 2>/dev/null | tr -d '[:space:]')
  [ "${N:-0}" -ge 6 ] 2>/dev/null && ok "Migrations applied ($N)" || warn "Migrations" "run: bash scripts/migrate.sh"
else warn "Postgres" "not running: docker compose -f infra/docker-compose.dev.yml up -d"; fi
curl -fsS -m 3 http://localhost:8000/healthz >/dev/null 2>&1 && ok "Backend /healthz" || warn "Backend" "not running (fine when not developing): uv run uvicorn app.main:app --reload in apps/api"
curl -fsS -m 3 http://localhost:8000/config.json >/dev/null 2>&1 && ok "Backend /config.json" || warn "Backend /config.json" "not running, or config failed pydantic validation (check uvicorn output)"
curl -fsS -m 3 http://localhost:5173 >/dev/null 2>&1 && ok "Frontend dev server" || warn "Frontend" "not running: pnpm -C apps/web dev"

hdr "RESULT"
printf "  PASS=%d WARN=%d FAIL=%d\n" "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -eq 0 ]; then printf "\n\xE2\x9C\x85 Local development environment verified.\nReady to start development.\n"; exit 0
else printf "\n\xE2\x9D\x8C %d check(s) failed. Fix FAIL lines and re-run.\n" "$FAIL"; exit 1; fi
