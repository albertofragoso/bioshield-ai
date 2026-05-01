# ChromaDB Integration Test Snapshot

Minimal ChromaDB collection with 8 Nutella ingredient embeddings.
Used by `docker-compose.integration.yml` (mounted read-only at `/data/chroma_db`).

## When to regenerate

- You change the embedding model (`USE_LOCAL_EMBEDDINGS`, `GEMINI_EMBEDDING_MODEL`, or `BGE_MODEL_NAME`).
  Changing models changes vector dimensions — the old collection becomes incompatible.
  See also: `docs/embedding-strategy.md` §1.
- You add ingredients to `NUTELLA_INGREDIENTS` in `scripts/seed_chroma_integration.py`.
- ChromaDB upgrades its on-disk format.

## How to regenerate

From the repo root (requires `GEMINI_API_KEY` in `backend/.env`, or set `USE_LOCAL_EMBEDDINGS=true`):

```bash
rm -rf tests/fixtures/chroma-seed
python scripts/seed_chroma_integration.py --output tests/fixtures/chroma-seed
git add tests/fixtures/chroma-seed
git commit -m "chore(integration): regenerate chroma-seed snapshot"
```

The script reads embedding settings from `backend/.env` and uses the active model.
Switch models by changing `USE_LOCAL_EMBEDDINGS` in `backend/.env` before running.
