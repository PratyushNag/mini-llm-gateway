# Hermes

Production-oriented LLM control plane for routing, retries, budgets, caching, streaming, and request visibility.

Hermes is an infrastructure platform for managing LLM traffic. It exposes an OpenAI-compatible chat endpoint, applies gateway-owned routing and fallback policy, tracks cost and latency, persists request and attempt logs, supports streaming, and includes a single walkthrough script for exercising the platform end to end without a frontend.

## What This Repo Provides

This repository provides the backend core of Hermes:

- an OpenAI-compatible `POST /v1/chat/completions` gateway endpoint
- config-driven model routing for `model=auto`
- retry and fallback across model candidates
- per-project API key authentication
- budget checks and per-request cost caps
- Redis-backed caching for eligible non-streaming requests
- request-level and attempt-level logs in Postgres
- streaming support with persisted final usage
- Prometheus metrics and structured JSON logging
- one deterministic walkthrough script that demonstrates all major runtime branches

This makes the repo useful as:

- a production-oriented LLM gateway/control-plane backend
- a reference implementation for policy-driven LLM request handling
- a portfolio project for LLM infra / gateway / control-plane roles

## What This Repo Does Not Yet Provide

Hermes is positioned as a production platform backend, but this repository intentionally does not yet include every surrounding platform surface. Today it does not include:

- admin APIs for creating projects, rotating keys, or changing budgets
- a web dashboard or frontend
- Alembic migrations and full schema evolution workflows
- rate limiting, quota enforcement, or abuse protection
- multi-provider integrations beyond OpenRouter
- advanced deployment manifests or CI/CD pipelines
- full production hardening around secrets, tenancy, and operational controls

Those omissions are deliberate. The repo is focused on the request path, policy layer, persistence model, and observability story.

## Why This Repo Exists

Hermes was built to represent the kind of problems LLM infrastructure teams care about:

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
- one walkthrough script that demonstrates success, fallback, budget rejection, cache, and streaming on top of the same platform APIs

## Current Scope

Today, Hermes is strongest in the core control-plane path:

- one FastAPI service
- one upstream integration layer targeting OpenRouter
- one Postgres-backed persistence layer
- one Redis-backed cache layer
- one demo project seeded locally
- one walkthrough script as the primary showcase path

If you approach the repo with that frame, the design decisions make more sense: the backend core is intentionally focused, while the surrounding platform surfaces are left for the next layer of expansion.

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

Swagger docs are available at `http://127.0.0.1:8000/docs`, but the walkthrough script is the fastest way to see Hermes behave like a real control plane.

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

If you want to use Hermes directly instead of the walkthrough, send requests to:

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

When `DEMO_UPSTREAM_MODE=mock`, Hermes can be demoed locally without an OpenRouter API key. Switching to real OpenRouter traffic is a config change, not a code change.

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
- Hermes owns model-level fallback. OpenRouter still handles provider-level routing under the selected model.

## Missing Next

If this were being pushed from strong MVP to production readiness, the next additions would be:

- admin/project management APIs
- key rotation and revocation flows
- migration management with Alembic
- rate limiting and quota enforcement
- stronger deployment and operational docs
- broader integration and end-to-end test coverage
