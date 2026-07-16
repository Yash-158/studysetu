# CONFIG.md - The Configuration System
Principle: if something can change, it changes in exactly one YAML file in config/: never in code.

## Layout (one file per subsystem)
app.yaml (product, branding, feature flags, locales) · ai.yaml (chains, models, cache, quotas, embedding_dim) · auth.yaml (JWT TTLs, activation, anomaly policy, session) · database.yaml (pool, BKT params, decay) · storage.yaml (provider, dirs, retention) · logging.yaml · cache.yaml (memory|redis) · analytics.yaml (thresholds) · email.yaml (none|resend) · security.yaml (assessment integrity flags) · ocr.yaml + offline.yaml (Phase 2, pre-built) · deployment.yaml (domains, CORS).

## Loading
Backend: app/core/config.py merges config/*.yaml -> Settings; validates at boot (invalid = refuse to start). Frontend: fetches /config.json (secret-free projection: product, branding, features, locales); branding colors injected as CSS variables, so rebranding = editing app.yaml.
Env overrides: `APP__<top>__<nested>=value` (e.g. `APP__ai__cache__demo_mode=true`). Secrets NEVER in YAML: .env only (see .env.example).

## Rules
Changing AI provider order = ai.yaml. Changing brand = app.yaml. Changing retention = storage.yaml. Enabling OCR/offline later = flipping features flags + their pre-built yaml. If a change requires editing code AND config, the design is wrong: fix the code to read config.

## Environments
Local: repo config/ + local .env. Production: same config/ (shipped in the image) + droplet .env + any APP__ overrides in the compose env. Divergence between environments is expressed ONLY through .env and APP__ overrides, never by editing YAML per environment.
