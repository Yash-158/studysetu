"""THE ONLY module that reads config files and environment (RULES.md #2).
Merges config/*.yaml into one Settings object; APP__file__key env overrides; crashes loudly on invalid config."""
from pathlib import Path
import os

import yaml
from pydantic import BaseModel, Field, ValidationError


class Product(BaseModel):
    name: str
    tagline: str
    org: str


class StatusTokens(BaseModel):
    success: str
    warning: str
    error: str
    success_text: str
    warning_text: str
    error_text: str
    surface: str


class PaletteColors(BaseModel):
    primary: str
    secondary: str
    accent: str
    background: str


class Palette(BaseModel):
    name: str
    colors: PaletteColors
    button_primary_bg: str
    neutral_track: str
    logo_colors: list[str]


class TypographyPairing(BaseModel):
    name: str
    body: str
    display: str
    google_fonts_url: str


class Spacing(BaseModel):
    xs: str
    sm: str
    md: str
    lg: str
    xl: str
    xxl: str = Field(alias="2xl")
    xxxl: str = Field(alias="3xl")


class Radius(BaseModel):
    sm: str
    md: str
    lg: str
    full: str


class Shadow(BaseModel):
    sm: str
    md: str
    lg: str


class Logo(BaseModel):
    path: str


class Branding(BaseModel):
    active_palette: str
    active_typography: str
    logo: Logo
    status: StatusTokens
    neutral_tracks: dict[str, dict[str, str]]
    palettes: dict[str, Palette]
    typography: dict[str, TypographyPairing]
    spacing: Spacing
    radius: Radius
    shadow: Shadow


class Features(BaseModel):
    explore: bool
    explore_weekly_quota: int
    typed_doubts: bool
    self_serve_teacher_tier: bool
    mentor_guidance: bool
    ocr: bool
    offline_sync: bool
    ai_pregrade: bool
    syllabus_import: bool


class Locales(BaseModel):
    enabled: list[str]
    default: str


class ModelSpec(BaseModel):
    model: str
    timeout_s: int
    temperature: float = 0.3  # low/deterministic default for structured JSON generation


class AiChains(BaseModel):
    # item_bank/session/dialogue/fast_text are NOT listed here - their provider order is resolved
    # dynamically at call time from ai.ai_primary_provider/ai_fallback_provider (gateway.py), not
    # declared statically. embeddings/ocr stay static: embeddings needs gemini's dedicated embed()
    # capability (no other onboarded provider implements it), ocr is dormant/vision-specific.
    embeddings: list[str]
    ocr: list[str]


class AiCache(BaseModel):
    enabled: bool
    prompt_version: str
    demo_mode: bool


class AiQuotas(BaseModel):
    max_concurrent_calls: int
    per_institution_daily_tokens: int


class AiItemBank(BaseModel):
    min_items: int
    max_items: int


class AiConfig(BaseModel):
    # Human-set knobs (docs/CONFIG.md): which of the 4 onboarded text providers leads the dynamic
    # chains, and which is the second try. The remaining two always serve as deeper fallback -
    # switching either value changes real behavior with zero code changes (gateway.py).
    ai_primary_provider: str
    ai_fallback_provider: str
    embedding_dim: int
    chains: AiChains
    models: dict[str, ModelSpec]
    cache: AiCache
    quotas: AiQuotas
    item_bank: AiItemBank


class Jwt(BaseModel):
    access_ttl_minutes: int
    refresh_ttl_days: int
    algorithm: str


class Activation(BaseModel):
    code_length: int
    code_ttl_hours: int


class PasswordPolicy(BaseModel):
    min_length: int


class Anomaly(BaseModel):
    concurrent_session_flag: str


class SessionPolicy(BaseModel):
    timeout_minutes: int
    inactivity_lock_minutes: int


class AuthConfig(BaseModel):
    jwt: Jwt
    activation: Activation
    password: PasswordPolicy
    anomaly: Anomaly
    session: SessionPolicy


class Pool(BaseModel):
    min_size: int
    max_size: int


class Bkt(BaseModel):
    p_init: float
    p_learn: float
    p_guess: float
    p_slip: float
    mastery_threshold: float


class Decay(BaseModel):
    confidence_halflife_days: int


class Diagnostic(BaseModel):
    probe_size: int
    easy: int
    medium: int
    hard: int


class DatabaseConfig(BaseModel):
    pool: Pool
    echo_sql: bool
    bkt: Bkt
    decay: Decay
    diagnostic: Diagnostic


class Domain(BaseModel):
    app: str
    api: str


class DeploymentConfig(BaseModel):
    domain: Domain
    cors_origins: list[str]
    api_base_url: str
    api_base_path: str


class EmailConfig(BaseModel):
    provider: str
    from_: str = Field(alias="from")


class SentrySettings(BaseModel):
    enabled: bool
    traces_sample_rate: float


class RequestLog(BaseModel):
    enabled: bool
    exclude_paths: list[str]


class LoggingConfig(BaseModel):
    level: str
    json_: bool = Field(alias="json")
    sentry: SentrySettings
    request_log: RequestLog


class Retention(BaseModel):
    doubt_photo_hours: int
    submissions: str
    materials: str


class MaterialsConfig(BaseModel):
    min_extractable_chars: int


class StorageConfig(BaseModel):
    provider: str
    upload_dir: str
    max_upload_mb: int
    retention: Retention
    cleanup_interval_minutes: int
    materials: MaterialsConfig


class CacheConfig(BaseModel):
    backend: str
    config_json_ttl_seconds: int
    dashboard_ttl_seconds: int


class WeeklyDigest(BaseModel):
    enabled: bool


class AnalyticsConfig(BaseModel):
    stuck_alert_minutes: int
    misconception_cluster_threshold: int
    weekly_digest: WeeklyDigest


class AssessmentSecurity(BaseModel):
    timer_enabled: bool
    autosave_seconds: int
    fullscreen_required: bool
    tab_switch_detection: str
    copy_paste_block: bool
    right_click_block: bool
    max_tab_switches_before_flag: int
    webcam_check: bool


class SecurityConfig(BaseModel):
    assessment: AssessmentSecurity


class OcrConfig(BaseModel):
    confidence_threshold: float
    max_image_mb: int


class OfflineConfig(BaseModel):
    sync_batch_size: int
    content_pack_max_mb: int


class RootConfig(BaseModel):
    product: Product
    branding: Branding
    features: Features
    locales: Locales
    ai: AiConfig
    auth: AuthConfig
    database: DatabaseConfig
    deployment: DeploymentConfig
    email: EmailConfig
    logging: LoggingConfig
    storage: StorageConfig
    cache: CacheConfig
    analytics: AnalyticsConfig
    security: SecurityConfig
    ocr: OcrConfig
    offline: OfflineConfig


class Settings:
    def __init__(self) -> None:
        self._data: dict = {}
        cfg_dir = Path(os.environ.get("APP_CONFIG_DIR", "config"))
        for f in sorted(cfg_dir.glob("*.yaml")):
            self._data.update(yaml.safe_load(f.read_text()) or {})
        self._apply_env_overrides()
        try:
            RootConfig.model_validate(self._data)
        except ValidationError as exc:
            raise SystemExit(f"Invalid configuration in {cfg_dir}/*.yaml:\n{exc}") from exc
        self.database_url = os.environ.get("DATABASE_URL", "")
        self.jwt_secret = os.environ.get("JWT_SECRET", "")
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = os.environ.get("SMTP_PORT", "")
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self.cerebras_api_key = os.environ.get("CEREBRAS_API_KEY", "")
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.prompts_dir = os.environ.get("APP_PROMPTS_DIR", "prompts")

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
