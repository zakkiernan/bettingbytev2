from __future__ import annotations

from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
except ModuleNotFoundError:  # pragma: no cover - optional local dependency
    class Limiter:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def limit(self, _rule: str) -> Callable[[F], F]:
            def decorator(func: F) -> F:
                return func

            return decorator

    def get_remote_address(*_args: Any, **_kwargs: Any) -> str:
        return "local"

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
auth_rate_limit = limiter.limit("10/minute")

__all__ = ["auth_rate_limit", "limiter"]
