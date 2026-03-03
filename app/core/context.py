from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
project_id_var: ContextVar[str | None] = ContextVar("project_id", default=None)


def set_request_context(*, request_id: str, project_id: str | None) -> None:
    request_id_var.set(request_id)
    project_id_var.set(project_id)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_project_id() -> str | None:
    return project_id_var.get()
