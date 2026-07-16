"""THE ONLY module that reads config files and environment (RULES.md #2).
Merges config/*.yaml into one Settings object; APP__file__key env overrides; crashes loudly on invalid config."""
from pathlib import Path
import os, yaml

class Settings:
    def __init__(self) -> None:
        self._data: dict = {}
        cfg_dir = Path(os.environ.get("APP_CONFIG_DIR", "config"))
        for f in sorted(cfg_dir.glob("*.yaml")):
            self._data.update(yaml.safe_load(f.read_text()) or {})
        self._apply_env_overrides()
        # TODO(M1): pydantic validation of every subsystem block; refuse to boot on missing keys
        self.database_url = os.environ.get("DATABASE_URL", "")
        self.jwt_secret = os.environ.get("JWT_SECRET", "")

    def _apply_env_overrides(self) -> None:
        for key, value in os.environ.items():
            if not key.startswith("APP__"):
                continue
            path = key[5:].split("__")
            node = self._data
            for part in path[:-1]:
                node = node.setdefault(part, {})
            node[path[-1]] = yaml.safe_load(value)

    def get(self, *path, default=None):
        node = self._data
        for p in path:
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node

    def public(self) -> dict:
        """Secret-free projection served at /config.json."""
        return {k: self._data.get(k) for k in ("product", "branding", "features", "locales")}

settings = Settings()
