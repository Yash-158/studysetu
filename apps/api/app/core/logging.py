"""Structured logging + Sentry wiring, driven by config/logging.yaml. No print() anywhere else."""
import os
import sys

import sentry_sdk
from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.get("logging", "level", default="INFO"),
        serialize=bool(settings.get("logging", "json", default=True)),
    )

    sentry_cfg = settings.get("logging", "sentry", default={}) or {}
    dsn = os.environ.get("SENTRY_DSN_API", "")
    if not sentry_cfg.get("enabled"):
        return
    if not dsn:
        logger.warning("logging.sentry.enabled is true but SENTRY_DSN_API is unset; Sentry disabled")
        return
    sentry_sdk.init(dsn=dsn, traces_sample_rate=sentry_cfg.get("traces_sample_rate", 0.0))
