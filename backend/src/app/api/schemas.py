from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    detail: str | list[str]


class SolveRequest(BaseModel):
    problem: dict[str, Any]


class ValidateResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectCreateRequest(ProjectBase):
    problem: dict[str, Any]


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    problem: dict[str, Any] | None = None


class ProjectSummaryResponse(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectSummaryResponse):
    problem: dict[str, Any]
    last_solution: dict[str, Any] | None = None


class SolveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
