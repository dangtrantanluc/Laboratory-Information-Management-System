"""Schemas RBAC (M7.2)."""
from pydantic import BaseModel


class InvalidateCacheOut(BaseModel):
    invalidated: bool


class InvalidateCacheResponse(BaseModel):
    success: bool
    data: InvalidateCacheOut
