.PHONY: eval dev down build test lint fmt shell lock inspector db-up db-down db-reset prod-build

# Dev containers run on the host's native architecture (fast on Apple Silicon), even if the
# shell sets DOCKER_DEFAULT_PLATFORM. prod-build pins linux/amd64 explicitly for Cloud Run.
unexport DOCKER_DEFAULT_PLATFORM

RUN := docker compose run --rm app

dev:            ## Start the server with hot reload on http://localhost:8000/mcp
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

test:           ## Run tests in the container
	$(RUN) pytest -q

eval:           ## Real-model LLM evals (needs ANTHROPIC_API_KEY; costs a few cents)
	$(RUN) pytest -v -m eval -o log_cli=true -o log_cli_level=INFO tests/evals

lint:           ## Lint + format check in the container
	$(RUN) sh -c "ruff check . && ruff format --check ."

fmt:
	$(RUN) sh -c "ruff format . ; ruff check --fix ."

shell:
	$(RUN) bash

lock:           ## Update uv.lock inside the container (after editing pyproject.toml)
	$(RUN) uv lock

inspector:      ## MCP Inspector (host Node) — connect to http://localhost:8000/mcp
	npx -y @modelcontextprotocol/inspector

db-up:          ## Local Supabase (Docker, via Supabase CLI)
	supabase start

db-down:
	supabase stop

db-reset:
	supabase db reset

prod-build:     ## Build the Cloud Run image locally (amd64, as Cloud Run requires)
	docker build --platform linux/amd64 --target prod -t ai-makan-agent:prod .
