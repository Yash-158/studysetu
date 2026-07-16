# config/ - one file per subsystem. Nothing is hardcoded.
Loaders merge all *.yaml here into one namespaced Settings object (backend: app/core/config.py; frontend: GET /config.json, secrets stripped). Env overrides: APP__<file>__<key>=value (e.g. APP__ai__chains__dialogue). Copy *.example.yaml -> *.yaml locally; prod configs live on the droplet.
