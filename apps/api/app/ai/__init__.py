"""AI facade: the ONLY import surface for feature code (RULES.md #1).
async def generate(task, **ctx)   # task selects prompt file + chain from config/ai.yaml
async def embed(texts) -> list[list[float]]
async def ocr(image_bytes)        # dormant until features.ocr
Gateway contract (gateway.py): lookup generated_artifacts by cache_key BEFORE any provider call;
write artifact + ai_invocations row AFTER; per-provider timeout; failover down the chain; demo_mode serves demo_cache first."""
