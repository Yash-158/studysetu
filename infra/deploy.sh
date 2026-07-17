#!/usr/bin/env bash
# Runs ON the droplet (invoked by deploy.yml over SSH). Sequence: pull -> up -> migrate -> health -> rollback on fail.
# Caddy/TLS/ports 80+443 are NOT part of this stack (see ../caffeineclause-edge); health is checked
# inside the container, not via a public port.
set -euo pipefail
cd /home/deploy/studysetu
PREV_TAG=$(cat .current_tag 2>/dev/null || echo "")
docker compose pull
TAG="${TAG:?TAG required}" docker compose up -d
docker compose exec -T api bash -lc "cd /srv && bash scripts/migrate.sh"

# ponytail: fixed sleep raced a slow-starting api image and false-failed a healthy deploy;
# poll instead of guessing a sleep duration, upgrade to a real readiness probe if this still flakes.
wait_healthy() {
  local svc="$1"; shift
  for _ in $(seq 1 20); do
    docker compose exec -T "$svc" "$@" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

if ! wait_healthy api curl -fsS http://localhost:8000/healthz; then
  echo "healthcheck FAILED - rolling back to ${PREV_TAG:-latest}"
  [ -n "$PREV_TAG" ] && TAG="$PREV_TAG" docker compose up -d
  exit 1
fi
# 127.0.0.1, not localhost: busybox wget in nginx:alpine resolves localhost to ::1 first, but the
# read-only-mounted default.conf has no "listen [::]:80" so nginx only binds IPv4.
if ! wait_healthy web wget -q -O- http://127.0.0.1/; then
  echo "web healthcheck FAILED - rolling back to ${PREV_TAG:-latest}"
  [ -n "$PREV_TAG" ] && TAG="$PREV_TAG" docker compose up -d
  exit 1
fi
echo "$TAG" > .current_tag
echo "deployed $TAG"
