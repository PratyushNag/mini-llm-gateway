from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.ids import new_key_id, new_project_id
from app.core.security import api_key_prefix, hash_api_key, verify_api_key
from app.db.models import ProjectApiKeyModel, ProjectModel
from app.domain.entities import ProjectContext


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_project_by_api_key(self, api_key: str) -> ProjectContext:
        prefix = api_key_prefix(api_key)
        query = (
            select(ProjectApiKeyModel, ProjectModel)
            .join(ProjectModel, ProjectApiKeyModel.project_id == ProjectModel.id)
            .where(ProjectApiKeyModel.key_prefix == prefix)
            .where(ProjectApiKeyModel.status == "active")
            .where(ProjectModel.status == "active")
        )
        rows = (await self._session.execute(query)).all()
        for key_model, project_model in rows:
            if verify_api_key(api_key, key_model.key_hash):
                key_model.last_used_at = datetime.now(UTC)
                await self._session.commit()
                return ProjectContext(
                    project_id=project_model.id,
                    project_name=project_model.name,
                    default_route_policy=project_model.default_route_policy,
                    monthly_budget_usd=Decimal(project_model.monthly_budget_usd),
                    per_request_cap_usd=(
                        Decimal(project_model.per_request_cap_usd)
                        if project_model.per_request_cap_usd is not None
                        else None
                    ),
                    allow_body_capture=project_model.allow_body_capture,
                    api_key_id=key_model.id,
                )
        raise AuthenticationError()

    async def create_demo_project(
        self,
        *,
        name: str,
        api_key: str,
        default_route_policy: str,
        monthly_budget_usd: Decimal,
        per_request_cap_usd: Decimal | None,
        allow_body_capture: bool,
    ) -> ProjectContext:
        existing = await self.get_by_name(name)
        if existing is not None:
            return existing

        project_model = ProjectModel(
            id=new_project_id(),
            name=name,
            default_route_policy=default_route_policy,
            monthly_budget_usd=monthly_budget_usd,
            per_request_cap_usd=per_request_cap_usd,
            allow_body_capture=allow_body_capture,
        )
        api_key_model = ProjectApiKeyModel(
            id=new_key_id(),
            project_id=project_model.id,
            key_prefix=api_key_prefix(api_key),
            key_hash=hash_api_key(api_key),
            description="Seeded demo API key",
        )
        self._session.add(project_model)
        self._session.add(api_key_model)
        await self._session.commit()
        return ProjectContext(
            project_id=project_model.id,
            project_name=project_model.name,
            default_route_policy=project_model.default_route_policy,
            monthly_budget_usd=monthly_budget_usd,
            per_request_cap_usd=per_request_cap_usd,
            allow_body_capture=allow_body_capture,
            api_key_id=api_key_model.id,
        )

    async def get_by_name(self, name: str) -> ProjectContext | None:
        query = (
            select(ProjectApiKeyModel, ProjectModel)
            .join(ProjectModel, ProjectApiKeyModel.project_id == ProjectModel.id)
            .where(ProjectModel.name == name)
            .limit(1)
        )
        row = (await self._session.execute(query)).first()
        if row is None:
            return None
        key_model, project_model = row
        return ProjectContext(
            project_id=project_model.id,
            project_name=project_model.name,
            default_route_policy=project_model.default_route_policy,
            monthly_budget_usd=Decimal(project_model.monthly_budget_usd),
            per_request_cap_usd=(
                Decimal(project_model.per_request_cap_usd)
                if project_model.per_request_cap_usd is not None
                else None
            ),
            allow_body_capture=project_model.allow_body_capture,
            api_key_id=key_model.id,
        )
