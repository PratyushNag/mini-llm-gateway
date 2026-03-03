from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import typer

from app.core.config import get_settings

app = typer.Typer(help="Run the full llm-gateway demo walkthrough.")


@dataclass(frozen=True, slots=True)
class DemoScenario:
    name: str
    description: str
    payload: dict[str, Any]
    headers: dict[str, str]


SCENARIOS: dict[str, DemoScenario] = {
    "success": DemoScenario(
        name="success",
        description="Standard request with routing and logging visible.",
        payload={
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are concise and technical."},
                {"role": "user", "content": "Explain why gateways need retry policy."},
            ],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 180,
        },
        headers={"X-Gateway-Cache-Mode": "bypass"},
    ),
    "fallback": DemoScenario(
        name="fallback",
        description="First attempt fails in demo mode, second candidate succeeds.",
        payload={
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are concise and technical."},
                {"role": "user", "content": "Show a demo of model fallback."},
            ],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 180,
        },
        headers={"X-Demo-Scenario": "fallback"},
    ),
    "budget_reject": DemoScenario(
        name="budget_reject",
        description="Request is rejected before any upstream call due to cap.",
        payload={
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are concise and technical."},
                {"role": "user", "content": "Trigger a budget preflight rejection."},
            ],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 180,
        },
        headers={"X-Gateway-Max-Cost-USD": "0.000001"},
    ),
    "cache_hit": DemoScenario(
        name="cache_hit",
        description="First call populates the cache and second call hits it.",
        payload={
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are concise and technical."},
                {"role": "user", "content": "Demonstrate cache reuse for this prompt."},
            ],
            "stream": False,
            "temperature": 0.0,
            "max_tokens": 120,
        },
        headers={"X-Gateway-Cache-Mode": "read_write"},
    ),
    "streaming": DemoScenario(
        name="streaming",
        description="Stream chunks to the client and persist final usage.",
        payload={
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are concise and technical."},
                {"role": "user", "content": "Stream a short explanation of latency tracking."},
            ],
            "stream": True,
            "temperature": 0.2,
            "max_tokens": 120,
        },
        headers={},
    ),
}


def format_request_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"  Request ID: {summary['request_id']}",
            f"  Status: {summary['status']}",
            f"  Resolved model: {summary.get('resolved_model')}",
            f"  Cache: {summary['cache_status']}",
            f"  Latency: {summary['latency_ms']} ms",
            f"  Total tokens: {summary['total_tokens']}",
            f"  Cost: ${summary['cost_usd']}",
        ]
    )


def format_attempts(detail: dict[str, Any]) -> str:
    if not detail.get("attempts"):
        return "  No upstream attempts were executed."
    lines: list[str] = []
    for attempt in detail["attempts"]:
        lines.append(
            "  "
            f"Attempt {attempt['attempt_index']}: {attempt['candidate_model']} -> "
            f"{attempt['status']} ({attempt['failure_kind']}) in {attempt['latency_ms']} ms"
        )
    return "\n".join(lines)


def _base_url() -> str:
    settings = get_settings()
    host = settings.api_host if settings.api_host != "0.0.0.0" else "127.0.0.1"
    return f"http://{host}:{settings.api_port}"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.demo_project_api_key}",
        "Content-Type": "application/json",
    }


def _print_section(title: str) -> None:
    typer.echo("")
    typer.echo("=" * 72)
    typer.echo(title)
    typer.echo("=" * 72)


def _pause(interactive: bool, pause_seconds: float) -> None:
    if interactive:
        typer.echo("")
        typer.confirm("Continue?", abort=False, default=True)
        return
    if pause_seconds > 0:
        time.sleep(pause_seconds)


def _ensure_gateway_ready(client: httpx.Client) -> None:
    health = client.get(f"{_base_url()}/healthz")
    health.raise_for_status()
    ready = client.get(f"{_base_url()}/readyz")
    ready.raise_for_status()


def _fetch_log_detail(client: httpx.Client, request_id: str) -> dict[str, Any]:
    response = client.get(f"{_base_url()}/v1/logs/{request_id}", headers=_headers())
    response.raise_for_status()
    return response.json()


def _print_detail(detail: dict[str, Any]) -> None:
    typer.echo("Final:")
    typer.echo(format_request_summary(detail))
    typer.echo("Attempts:")
    typer.echo(format_attempts(detail))


def _run_standard_scenario(client: httpx.Client, scenario: DemoScenario) -> None:
    typer.echo(f"Scenario: {scenario.name}")
    typer.echo(f"What it proves: {scenario.description}")
    response = client.post(
        f"{_base_url()}/v1/chat/completions",
        headers={**_headers(), **scenario.headers},
        json=scenario.payload,
    )
    if response.status_code >= 400:
        typer.echo("Request failed:")
        typer.echo(json.dumps(response.json(), indent=2))
        error_body = response.json()
        request_id = error_body.get("error", {}).get("request_id")
        if request_id:
            typer.echo("")
            typer.echo("Persisted gateway record:")
            _print_detail(_fetch_log_detail(client, request_id))
        return
    request_id = response.headers["X-Gateway-Request-Id"]
    _print_detail(_fetch_log_detail(client, request_id))


def _run_cache_hit(client: httpx.Client, scenario: DemoScenario) -> None:
    typer.echo("Scenario: cache_hit")
    typer.echo(f"What it proves: {scenario.description}")
    first_response = client.post(
        f"{_base_url()}/v1/chat/completions",
        headers={**_headers(), **scenario.headers},
        json=scenario.payload,
    )
    first_response.raise_for_status()
    second_response = client.post(
        f"{_base_url()}/v1/chat/completions",
        headers={**_headers(), **scenario.headers},
        json=scenario.payload,
    )
    second_response.raise_for_status()

    first_request_id = first_response.headers["X-Gateway-Request-Id"]
    second_request_id = second_response.headers["X-Gateway-Request-Id"]

    typer.echo("First request:")
    _print_detail(_fetch_log_detail(client, first_request_id))
    typer.echo("")
    typer.echo("Second request:")
    _print_detail(_fetch_log_detail(client, second_request_id))


def _run_streaming(client: httpx.Client, scenario: DemoScenario) -> None:
    typer.echo("Scenario: streaming")
    typer.echo(f"What it proves: {scenario.description}")
    request_id = ""
    with client.stream(
        "POST",
        f"{_base_url()}/v1/chat/completions",
        headers={**_headers(), **scenario.headers},
        json=scenario.payload,
    ) as response:
        response.raise_for_status()
        request_id = response.headers["X-Gateway-Request-Id"]
        typer.echo("Streaming preview:")
        for line in response.iter_lines():
            if not line or line == "data: [DONE]":
                continue
            typer.echo(f"  {line[:140]}")

    typer.echo("")
    typer.echo("Persisted gateway record:")
    _print_detail(_fetch_log_detail(client, request_id))


@app.command()
def run(
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Pause between sections and wait for confirmation.",
    ),
    pause_seconds: float = typer.Option(
        0.0,
        "--pause-seconds",
        min=0.0,
        help="Sleep between sections when not using interactive mode.",
    ),
) -> None:
    settings = get_settings()
    typer.echo("LLM Gateway demo walkthrough")
    typer.echo(f"Base URL: {_base_url()}")
    typer.echo(f"Demo project: {settings.demo_project_name}")
    typer.echo(f"Demo mode: {settings.demo_upstream_mode}")

    with httpx.Client(timeout=90.0) as client:
        _ensure_gateway_ready(client)

        _print_section("1. Success path")
        _run_standard_scenario(client, SCENARIOS["success"])
        _pause(interactive, pause_seconds)

        _print_section("2. Deterministic fallback")
        _run_standard_scenario(client, SCENARIOS["fallback"])
        _pause(interactive, pause_seconds)

        _print_section("3. Budget rejection")
        _run_standard_scenario(client, SCENARIOS["budget_reject"])
        _pause(interactive, pause_seconds)

        _print_section("4. Cache miss then cache hit")
        _run_cache_hit(client, SCENARIOS["cache_hit"])
        _pause(interactive, pause_seconds)

        _print_section("5. Streaming")
        _run_streaming(client, SCENARIOS["streaming"])


if __name__ == "__main__":
    app()
