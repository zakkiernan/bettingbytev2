from __future__ import annotations

from datetime import datetime
from typing import Literal

from api.schemas.base import APIModel


class UserResponse(APIModel):
    id: int
    email: str
    tier: Literal["FREE", "PREMIUM", "PRO"]
    is_active: bool
    created_at: datetime


class AuthResponse(APIModel):
    user: UserResponse
    token: str
