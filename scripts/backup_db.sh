#!/usr/bin/env bash
# Nightly on the droplet (root cron): dump into backups_data volume, keep 7, weekly uploads tar.
set -euo pipefail
cd /home/deploy/studysetu
docker compose exec -T postgres bash -lc 'pg_dump -U app -Fc appdb | gzip > /backups/appdb_$(date +%F).dump.gz'
docker compose exec -T postgres bash -lc 'ls -1t /backups/appdb_*.dump.gz | tail -n +8 | xargs -r rm'
if [ "$(date +%u)" = "7" ]; then docker run --rm -v studysetu_uploads_data:/u -v studysetu_backups_data:/b alpine tar czf /b/uploads_$(date +%F).tar.gz -C /u .; fi
echo "backup complete"
