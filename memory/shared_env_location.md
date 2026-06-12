---
name: Shared .env location
description: All API keys live in one .env file at the Bellaciao Content/ parent folder, shared across every project under it
type: project
---

API credentials for the script_engine (and any sibling project under `Bellaciao Content/`) live in a **single shared `.env` file at `Bellaciao Content/.env`** — NOT in `script_engine/.env`. The example template lives at `Bellaciao Content/.env.example`.

Every Python module that needs keys loads it explicitly with:

```python
load_dotenv(Path(__file__).parent.parent / ".env")
```

This is wired in: `engine.py`, `strategy.py`, `apify_scout.py`, `quality_supervisor.py`. Required key: `ANTHROPIC_API_KEY` (judge + strategy). Optional: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `APIFY_TOKEN`, `APIFY_*_ACTOR_ID`.

**Why:** The user keeps multiple Bellaciao projects (script_engine, Agents, Scripts, Creatives, Master Documents) under the same `Bellaciao Content/` folder and wanted ONE credentials file shared across all of them — no per-project `.env` copies, no drift between projects when a key rotates.

**How to apply:** When adding a new module that needs API keys, do not call bare `load_dotenv()` and do not create a project-local `.env`. Always use `load_dotenv(Path(__file__).parent.parent / ".env")` so it resolves to the shared file. When adding a new sibling project under `Bellaciao Content/`, follow the same convention so it inherits the same credentials. If the user rotates a key, they only need to edit the one file at `Bellaciao Content/.env`.
