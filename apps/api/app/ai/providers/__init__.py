"""Shared provider contract. Each sibling module (claude.py/gemini.py/groq.py) is the ONLY place
allowed to import that provider's SDK/HTTP surface (RULES.md #1) and exposes:
    async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult
Feature code never imports these directly - only apps/api/app/ai/gateway.py does."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderResult:
    text: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """Raised for any provider-side failure (missing key, HTTP error, timeout, malformed
    response shape) so the gateway can uniformly log it and fail over - never a raw SDK
    exception, RULES.md #13 ("raw provider errors never reach users")."""
