from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

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
def register() -> AuthResponse:
    return AuthResponse(user=MOCK_USER, token="mock-register-token")


@router.post("/login", response_model=AuthResponse)
def login() -> AuthResponse:
    return AuthResponse(user=MOCK_USER, token="mock-login-token")


@router.get("/me", response_model=UserResponse)
def me() -> UserResponse:
    return MOCK_USER
