"""StudySetu API entrypoint. Infrastructure only: app factory, health, config.json, router mounting.
Business logic lives in app/modules/* and is implemented milestone-by-milestone (docs/PROMPTS.md)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.modules import auth as auth_module

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="StudySetu API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get("deployment", "cors_origins", default=[]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "service": "api", "version": app.version}

    @app.get("/config.json")
    async def public_config() -> dict:
        """Runtime config for the frontend: branding, features, locales. Secrets never pass here."""
        return settings.public()

    app.include_router(auth_module.router)
    # TODO(M2): mount app.modules.institutions.router
    # TODO(M3): mount app.modules.curriculum.router
    # TODO(M4): mount app.modules.assessment.router
    # TODO(M5): mount app.modules.learning.router
    # TODO(M6): mount app.modules.analytics.router
    # TODO(M7): mount app.modules.assignments.router
    # TODO(M8): mount app.modules.doubts.router, app.modules.explore.router
    return app

app = create_app()
