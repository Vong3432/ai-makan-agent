# AI Makan Agent

Meal-recommendation agent exposed as a remote MCP server. See [docs/SPEC.md](docs/SPEC.md) and [docs/plans](docs/plans/README.md).

## Prerequisites

- Docker Desktop
- Supabase CLI (for local database, from P1)
- Node.js (only for `make inspector`)

No Python needed on the host — everything runs in Docker.

## Run locally

Get the API keys first: [docs/SETUP_KEYS.md](docs/SETUP_KEYS.md).

```bash
cp .env.example .env
make dev            # http://localhost:8000/mcp, hot reload
make inspector      # in another terminal; connect to http://localhost:8000/mcp (Streamable HTTP)
```

## Common commands

| Command | What it does |
|---|---|
| `make test` | Run tests in the container |
| `make lint` / `make fmt` | Lint / auto-fix |
| `make lock` | Update `uv.lock` after editing `pyproject.toml` |
| `make shell` | Shell inside the dev container |
| `make db-up` / `make db-reset` | Local Supabase |
| `make prod-build` | Build the Cloud Run image |
