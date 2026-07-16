"""Structured logging + Sentry wiring, driven by config/logging.yaml. No print() anywhere else."""
def setup_logging() -> None:
    # TODO(M1): loguru JSON sink at settings.get("logging","level"); sentry_sdk.init(dsn=env SENTRY_DSN_API)
    pass
