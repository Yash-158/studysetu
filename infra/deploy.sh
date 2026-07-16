#!/usr/bin/env bash
# Runs ON the droplet (invoked by deploy.yml over SSH). Sequence: pull -> up -> migrate -> health -> rollback on fail.
set -euo pipefail
cd /home/deploy/app
PREV_TAG=$(cat .current_tag 2>/dev/null || echo "")
docker compose pull api
TAG="${TAG:?TAG required}" docker compose up -d
docker compose exec -T api bash -lc "cd /srv && bash scripts/migrate.sh"
sleep 3
if ! curl -fsS http://localhost:8000/healthz >/dev/null && ! docker compose exec -T api curl -fsS http://localhost:8000/healthz >/dev/null; then
  echo "healthcheck FAILED - rolling back to ${PREV_TAG:-latest}"
  [ -n "$PREV_TAG" ] && TAG="$PREV_TAG" docker compose up -d
  exit 1
fi
echo "$TAG" > .current_tag
echo "deployed $TAG"
