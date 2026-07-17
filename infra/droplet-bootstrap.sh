#!/usr/bin/env bash
# One-time (but safe to re-run) setup for a multi-project droplet. Run as root:
#   ssh root@64.227.177.181 'bash -s' < infra/droplet-bootstrap.sh
# Idempotent: every step checks current state before acting. Does NOT touch this project's
# docker compose stack or secrets - only the shared host-level prerequisites every project
# on this droplet needs (deploy user, Docker, firewall, the "edge" network, this repo's dir).
set -euo pipefail

DEPLOY_USER="deploy"
APP_DIR="/home/${DEPLOY_USER}/studysetu"

echo "== 1. deploy user =="
if id "$DEPLOY_USER" >/dev/null 2>&1; then
  echo "  deploy user already exists"
else
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG sudo "$DEPLOY_USER"
  echo "  created deploy user (no password - SSH key only)"
fi
if [ -d /root/.ssh ] && [ ! -d "/home/${DEPLOY_USER}/.ssh" ]; then
  rsync --archive --chown="${DEPLOY_USER}:${DEPLOY_USER}" /root/.ssh "/home/${DEPLOY_USER}/"
  echo "  copied root's authorized_keys to deploy (adjust later if you want a different key)"
fi

echo "== 2. SSH hardening =="
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
echo "  PermitRootLogin no, PasswordAuthentication no"

echo "== 3. firewall =="
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | sed 's/^/  /'

echo "== 4. fail2ban + unattended-upgrades =="
apt-get update -qq
apt-get install -y -qq fail2ban unattended-upgrades >/dev/null
systemctl enable --now fail2ban >/dev/null
echo "  fail2ban active"

echo "== 5. timezone =="
timedatectl set-timezone Asia/Kolkata
echo "  Asia/Kolkata"

echo "== 6. Docker =="
if command -v docker >/dev/null 2>&1; then
  echo "  docker already installed ($(docker --version))"
else
  curl -fsSL https://get.docker.com | sh
  echo "  docker installed"
fi
usermod -aG docker "$DEPLOY_USER"

echo "== 7. shared 'edge' Docker network =="
if docker network inspect edge >/dev/null 2>&1; then
  echo "  edge network already exists"
else
  docker network create edge
  echo "  created edge network"
fi

echo "== 8. per-project app directory =="
mkdir -p "$APP_DIR"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "$APP_DIR"
echo "  ${APP_DIR} ready"

echo
echo "Bootstrap complete. Next (manual, as documented in the report):"
echo "  1. As deploy: generate a GH-Actions-only SSH keypair, add its public half to"
echo "     ~deploy/.ssh/authorized_keys, paste the private half into DROPLET_SSH_KEY."
echo "  2. Place ${APP_DIR}/.env (chmod 600) with real secrets."
echo "  3. Set up ../caffeineclause-edge on this droplet (its own compose + Caddyfile) if not already."
echo "  4. bash scripts/verify_server.sh to confirm everything above."
