# apps/api - Backend (FastAPI modular monolith)
Created during SETUP_STEPS Step 5. Modules: auth, sync, probe, mastery, doubt, dashboard, storage, ai, rag.
Rules: provider SDKs only under app/ai/providers/; config reads only in app/config.py; file I/O only via StorageProvider.
