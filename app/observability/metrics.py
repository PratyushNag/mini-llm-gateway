from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNTER = Counter("gateway_requests_total", "Total gateway requests.", ["status"])
REQUEST_LATENCY = Histogram("gateway_request_latency_seconds", "Gateway request latency.")
ATTEMPT_COUNTER = Counter("gateway_upstream_attempts_total", "Total upstream attempts.", ["status"])
ATTEMPT_LATENCY = Histogram(
    "gateway_upstream_attempt_latency_seconds",
    "Upstream attempt latency.",
)
CACHE_HIT_COUNTER = Counter("gateway_cache_hits_total", "Total cache hits.")
BUDGET_REJECTION_COUNTER = Counter("gateway_budget_rejections_total", "Budget rejections.")
COST_COUNTER = Counter("gateway_cost_usd_total", "Accumulated USD cost.")
INTERNAL_OPERATION_LATENCY = Histogram(
    "gateway_internal_operation_seconds",
    "Latency for internal operations.",
    ["operation"],
)


def observe_request(status: str, latency_seconds: float, cost_usd: float) -> None:
    REQUEST_COUNTER.labels(status=status).inc()
    REQUEST_LATENCY.observe(latency_seconds)
    COST_COUNTER.inc(cost_usd)


def observe_attempt(status: str, latency_seconds: float) -> None:
    ATTEMPT_COUNTER.labels(status=status).inc()
    ATTEMPT_LATENCY.observe(latency_seconds)


def observe_cache_hit() -> None:
    CACHE_HIT_COUNTER.inc()


def observe_budget_rejection() -> None:
    BUDGET_REJECTION_COUNTER.inc()


def observe_internal_operation(operation: str, latency_seconds: float) -> None:
    INTERNAL_OPERATION_LATENCY.labels(operation=operation).observe(latency_seconds)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
