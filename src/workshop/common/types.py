"""Shared pydantic base models and pagination helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
