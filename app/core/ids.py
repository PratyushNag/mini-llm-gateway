from __future__ import annotations

from uuid import uuid4


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


def new_attempt_id() -> str:
    return f"att_{uuid4().hex}"


def new_project_id() -> str:
    return f"prj_{uuid4().hex}"


def new_key_id() -> str:
    return f"key_{uuid4().hex}"
