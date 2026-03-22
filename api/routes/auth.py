from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from api.rate_limit import auth_rate_limit
from api.schemas import AuthResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


MOCK_USER = UserResponse(
    id=1,
    email="demo@bettingbyte.dev",
    tier="FREE",
    is_active=True,
    created_at=datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc),
)


@router.post("/register", response_model=AuthResponse)
@auth_rate_limit
def register(request: Request) -> AuthResponse:
    return AuthResponse(user=MOCK_USER, token="mock-register-token")


@router.post("/login", response_model=AuthResponse)
@auth_rate_limit
def login(request: Request) -> AuthResponse:
    return AuthResponse(user=MOCK_USER, token="mock-login-token")


@router.get("/me", response_model=UserResponse)
@auth_rate_limit
def me(request: Request) -> UserResponse:
    return MOCK_USER
