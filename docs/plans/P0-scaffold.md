# P0 — Project scaffold & local dev loop

**Goal:** an empty-but-runnable FastMCP server you can connect to locally, with tests and lint wired up.
**Specs:** [Architecture](../specs/02-architecture.md)

## Tasks

- [x] **P0-T1** Init project with `uv` (Python 3.12+), `src/makan` package, `pyproject.toml`.
- [x] **P0-T2** Add deps: `fastmcp`, `pydantic`, `pydantic-settings`, `httpx`, `supabase`; dev deps: `pytest`, `pytest-asyncio`, `ruff`, `respx`.
- [x] **P0-T3** `config.py` with pydantic-settings; `.env.example` listing every variable (Supabase URL/keys, Google API key, LLM key, `AUTH_MODE=dev|supabase`, `RATE_LIMIT_ENABLED=false`).
- [x] **P0-T4** `server.py`: FastMCP app on Streamable HTTP with a `ping` tool.
- [x] **P0-T5** Dev-auth mode: when `AUTH_MODE=dev`, every request resolves to a fixed test `user_id`.
- [x] **P0-T6** Create the folder skeleton from the target layout (empty modules + `__init__.py`).
- [x] **P0-T7** `pytest` + `ruff` config; one smoke test calling `ping` via FastMCP's in-memory client.
- [x] **P0-T8** Multi-stage `Dockerfile`: `dev` target (deps + dev deps, source mounted, uvicorn `--reload`) and `prod` target (slim, non-root) — prod reused in P10.
- [x] **P0-T9** `compose.yaml`: `app` service (dev target, `./src` + `./tests` mounted, port 8000, `.env`), reaching local Supabase via `host.docker.internal`.
- [x] **P0-T10** `Makefile` targets that run inside Docker: `dev` (`docker compose up`), `test`, `lint`, `shell`, `inspector` (MCP Inspector against the container).
- [x] **P0-T11** Add `README.md` at repo root: prerequisites (Docker, Supabase CLI) and run instructions.

## Done when

- `make dev` starts the server in Docker with hot reload; MCP Inspector can call `ping`.
- `make test` and `make lint` pass inside the container.
- No Python install needed on the host.
