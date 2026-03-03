from __future__ import annotations

from enum import StrEnum


class RequestStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    STREAMING = "streaming"
    CLIENT_CANCELLED = "client_cancelled"


class AttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CacheStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    BYPASS = "BYPASS"


class FailureKind(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    UPSTREAM_429 = "upstream_429"
    UPSTREAM_5XX = "upstream_5xx"
    UPSTREAM_4XX = "upstream_4xx"
    DEMO_FORCED_TIMEOUT = "demo_forced_timeout"
    CLIENT_CANCELLED = "client_cancelled"
    UNKNOWN = "unknown"
