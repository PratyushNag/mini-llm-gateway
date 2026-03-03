from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    default_route_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    monthly_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    per_request_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    allow_body_capture: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    api_keys: Mapped[list[ProjectApiKeyModel]] = relationship(back_populates="project")


class ProjectApiKeyModel(Base):
    __tablename__ = "project_api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[ProjectModel] = relationship(back_populates="api_keys")


class LlmRequestModel(Base):
    __tablename__ = "llm_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    route_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stream: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cache_status: Mapped[str] = mapped_column(String(16), nullable=False)
    capture_body: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_body_redacted: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    response_body_redacted: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    attempts: Mapped[list[LlmAttemptModel]] = relationship(back_populates="request")


class LlmAttemptModel(Base):
    __tablename__ = "llm_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("llm_requests.id"), index=True, nullable=False
    )
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_model: Mapped[str] = mapped_column(String(255), nullable=False)
    actual_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    upstream_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    request: Mapped[LlmRequestModel] = relationship(back_populates="attempts")
