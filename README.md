# LLM Gateway

Lightweight LLM control plane built on top of OpenRouter for routing, retries, budgets, caching, and request visibility.

This repo is intentionally built as infra, not a chatbot app. It exposes an OpenAI-compatible chat endpoint, applies gateway-owned routing and fallback policy, tracks cost and latency, persists request and attempt logs, supports streaming, and includes a single walkthrough script that demos the full system without a frontend.

## Why This Repo Exists

I built this to showcase the kind of problems LLM infrastructure teams care about:

- routing requests across model candidates
- retrying and falling back on failure
- enforcing budget and cost controls
- making request behavior observable after the fact
- packaging all of that in a small, readable backend service

## Architecture

```text
CLI Demo Runner / API Client
  -> FastAPI Gateway
  -> Auth + Project Context
  -> Route Policy Engine
  -> Budget Guard
  -> Cache Service
  -> OpenRouter Client or Demo Failure Adapter
  -> Attempt Logger
  -> Request Logger
  -> Postgres / Redis
```

## Features

- `POST /v1/chat/completions` with OpenAI-compatible payloads
- `model=auto` route resolution from `config/routes.yml`
- model retry and fallback with per-attempt logging
- per-project API keys and scoped logs
- cost estimation and request cap enforcement
- Redis cache for eligible non-streaming requests
- `GET /v1/logs` and `GET /v1/logs/{id}` for request and attempt visibility
- streaming support with persisted final usage
- deterministic demo fault injection for reliable fallback demos
- one walkthrough script that demonstrates success, fallback, budget rejection, cache, and streaming

## Quickstart

1. Copy `.env.example` to `.env`.
2. Start dependencies:

```bash
docker compose up postgres redis -d
```

3. Install the app:

```bash
uv sync --extra dev
```

4. Install the git hook:

```bash
uv run pre-commit install
```

5. Seed the demo project:

```bash
uv run python -m scripts.seed_demo
```

6. Start the API:

```bash
uv run uvicorn app.main:app --reload
```

7. Run the full demo walkthrough:

```bash
uv run python -m scripts.demo_walkthrough
```

Swagger docs are available at `http://127.0.0.1:8000/docs`, but the walkthrough script is the primary showcase path.

## Demo Walkthrough

```bash
uv run python -m scripts.demo_walkthrough
```

The walkthrough runs all major gateway features in order:

- success path
- deterministic fallback
- budget rejection
- cache miss then cache hit
- streaming

The fallback step is deterministic in demo mode. It forces the first `gpt-4.1` attempt to fail with `demo_forced_timeout`, then falls through to `gpt-4o-mini`.

For a single live walkthrough that exercises every feature in order:

```bash
uv run python -m scripts.demo_walkthrough
```

Or with pauses between sections:

```bash
uv run python -m scripts.demo_walkthrough --interactive
```

If you want to use the gateway directly instead of the walkthrough, send requests to:

```text
POST /v1/chat/completions
GET /v1/logs
GET /v1/logs/{request_id}
```

## Example Output

```text
Scenario: fallback
Description: First attempt fails in demo mode, second candidate succeeds.
Final:
  Request ID: req_123
  Status: succeeded
  Resolved model: openai/gpt-4o-mini
  Cache: BYPASS
  Latency: 24 ms
  Total tokens: 232
  Cost: $0.000076
Attempts:
  Attempt 1: openai/gpt-4.1 -> failed (demo_forced_timeout) in 0 ms
  Attempt 2: openai/gpt-4o-mini -> succeeded (none) in 20 ms
```

## Example Log Detail

```json
{
  "request_id": "req_123",
  "route_policy": "balanced",
  "requested_model": "auto",
  "resolved_model": "openai/gpt-4o-mini",
  "status": "succeeded",
  "stream": false,
  "cache_status": "BYPASS",
  "attempt_count": 2,
  "latency_ms": 24,
  "prompt_tokens": 52,
  "completion_tokens": 180,
  "total_tokens": 232,
  "cost_usd": "0.000076",
  "attempts": [
    {
      "attempt_index": 1,
      "candidate_model": "openai/gpt-4.1",
      "status": "failed",
      "failure_kind": "demo_forced_timeout"
    },
    {
      "attempt_index": 2,
      "candidate_model": "openai/gpt-4o-mini",
      "status": "succeeded",
      "failure_kind": "none"
    }
  ]
}
```

## Configuration

- Route policy config: [`config/routes.yml`](/e:/Personal%20Projects/job-search/portkey-demo/config/routes.yml)
- Environment template: [` .env.example`](/e:/Personal%20Projects/job-search/portkey-demo/.env.example)

Important flags:

- `ENABLE_DEMO_MODE=true`
- `DEMO_UPSTREAM_MODE=mock`
- `DEMO_PROJECT_API_KEY=lgw_demo_local_key`

When `DEMO_UPSTREAM_MODE=mock`, the gateway can be demoed locally without an OpenRouter API key. Switching to real OpenRouter traffic is a config change, not a code change.

## Project Layout

```text
app/
  api/
  core/
  db/
  domain/
  observability/
  providers/
  repositories/
  services/
config/
scripts/
tests/
```

## Testing

```bash
uv run pytest
```

## Quality Gates

This repo uses `uv` for environment and dependency management, and `pre-commit` for local quality gates.

Before each commit, the hook runs:

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest`

Manual commands:

```bash
uv run ruff check .
uv run mypy .
uv run pytest
uv run pre-commit run --all-files
```

## Tradeoffs

- Tables are created automatically on startup for ease of demo. Full Alembic migrations can be added next without changing the service boundaries.
- Demo mode uses deterministic failure injection and a mock upstream adapter so the project is reviewable without third-party credentials.
- The gateway owns model-level fallback. OpenRouter still handles provider-level routing under the selected model.
