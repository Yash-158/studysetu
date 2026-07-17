#!/usr/bin/env bash
# Run ON the droplet as deploy: bash verify_server.sh
set -uo pipefail
PASS=0; FAIL=0; WARN=0
ok(){ printf "  \e[32m[PASS]\e[0m %s\n" "$1"; PASS=$((PASS+1)); }
bad(){ printf "  \e[31m[FAIL]\e[0m %s -- %s\n" "$1" "$2"; FAIL=$((FAIL+1)); }
warn(){ printf "  \e[33m[WARN]\e[0m %s -- %s\n" "$1" "$2"; WARN=$((WARN+1)); }
hdr(){ printf "\n\e[1m%s\e[0m\n" "$1"; }

hdr "1. OS & security"
. /etc/os-release 2>/dev/null; [ "${ID:-}" = ubuntu ] && [[ "${VERSION_ID:-}" == 24.* ]] && ok "Ubuntu $VERSION_ID" || warn "OS" "expected Ubuntu 24.x"
S=$(sudo sshd -T 2>/dev/null||true)
echo "$S" | grep -q "permitrootlogin no" && ok "Root SSH off" || bad "PermitRootLogin" "must be no"
echo "$S" | grep -q "passwordauthentication no" && ok "Password SSH off" || bad "PasswordAuthentication" "must be no"
sudo ufw status 2>/dev/null | grep -q "Status: active" && ok "ufw active" || bad "ufw" "enable it"
X=$(sudo ufw status 2>/dev/null | grep ALLOW | grep -vE "22|80|443|OpenSSH" | wc -l); [ "$X" -eq 0 ] && ok "Only 22/80/443" || bad "ufw" "unexpected ports open"
systemctl is-active --quiet fail2ban && ok "fail2ban" || bad "fail2ban" "enable it"
[ "$(timedatectl show -p Timezone --value)" = "Asia/Kolkata" ] && ok "TZ Asia/Kolkata" || warn "TZ" "set-timezone Asia/Kolkata"

hdr "2. Docker stack"
command -v docker >/dev/null && ok "Docker" || bad "Docker" "install"
docker compose version >/dev/null 2>&1 && ok "Compose" || bad "Compose" "plugin missing"
docker info >/dev/null 2>&1 && ok "Docker without sudo" || bad "Docker perms" "usermod -aG docker deploy"
docker network inspect edge >/dev/null 2>&1 && ok "edge network exists" || bad "edge network" "docker network create edge (see infra/droplet-bootstrap.sh)"
cd /home/deploy/studysetu 2>/dev/null || { bad "~/studysetu" "missing app dir"; }
if docker compose ps --format '{{.Service}}' 2>/dev/null | grep -q postgres; then
  docker compose exec -T postgres pg_isready -U app >/dev/null 2>&1 && ok "Postgres ready" || bad "Postgres" "not ready"
  N=$(docker compose exec -T postgres psql -U app -d appdb -tAc "SELECT count(*) FROM schema_migrations" 2>/dev/null | tr -d '[:space:]')
  [ "${N:-0}" -ge 6 ] 2>/dev/null && ok "Migrations applied ($N)" || warn "Migrations" "will apply on first deploy"
else warn "Postgres" "stack not up yet (pre-first-deploy)"; fi
ss -tlnp 2>/dev/null | grep -q ":5432 " && bad "Postgres exposure" "5432 public - must stay internal" || ok "Postgres not exposed"
ss -tlnp 2>/dev/null | grep -qE ":80 |:443 " && bad "Ports 80/443" "must NOT be bound by this stack - owned by caffeineclause-edge" || ok "No 80/443 bound by this stack"
docker compose exec -T api curl -fsS -m 5 http://localhost:8000/healthz >/dev/null 2>&1 && ok "API /healthz (in-container)" || warn "API health" "not up yet"

hdr "3. Volumes, env, backups"
for v in studysetu_pg_data studysetu_uploads_data studysetu_backups_data; do
  docker volume inspect "$v" >/dev/null 2>&1 && ok "volume $v" || warn "volume $v" "created on first compose up"; done
if [ -f /home/deploy/studysetu/.env ]; then P=$(stat -c %a /home/deploy/studysetu/.env); [ "$P" -le 640 ] && ok ".env perms $P" || warn ".env" "chmod 600"
  for k in DATABASE_URL JWT_SECRET POSTGRES_PASSWORD; do grep -q "^$k=..\+" /home/deploy/studysetu/.env && ok "env $k set" || bad "env $k" "empty in .env"; done
else bad ".env" "place /home/deploy/studysetu/.env"; fi
ls /var/lib/docker/volumes/studysetu_backups_data/_data/appdb_*.dump.gz >/dev/null 2>&1 && ok "Backups exist" || warn "Backups" "cron not run yet (scripts/backup_db.sh)"
crontab -l 2>/dev/null | grep -q backup_db && ok "Backup cron installed" || warn "Backup cron" "install nightly backup_db.sh"

hdr "4. Resources & network"
D=$(df -h / | awk 'NR==2{print $5}' | tr -d %); [ "$D" -lt 80 ] && ok "Disk ${D}%" || bad "Disk" "${D}% - prune"
M=$(free -m | awk '/Mem:/{print $7}'); [ "$M" -gt 500 ] && ok "RAM avail ${M}MB" || warn "RAM" "low: ${M}MB"
curl -fsS -m 8 https://api.github.com >/dev/null && ok "Outbound HTTPS" || bad "Internet" "no egress"

hdr "RESULT"
printf "  PASS=%d WARN=%d FAIL=%d\n" "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -eq 0 ]; then printf "\n\xE2\x9C\x85 Production server verified.\nReady for deployment.\n"; exit 0
else printf "\n\xE2\x9D\x8C %d check(s) failed.\n" "$FAIL"; exit 1; fi
