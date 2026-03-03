from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.context import get_project_id, get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "project_id": get_project_id(),
        }
        extra_payload = getattr(record, "extra_payload", None)
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
