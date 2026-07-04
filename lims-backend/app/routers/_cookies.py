"""Helper set/clear refresh_token cookie — HttpOnly Secure SameSite=Strict (§0.3 contract)."""
from fastapi import Response

from app.config import settings

REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, refresh_token_raw: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token_raw,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,  # dev (http) cần secure=False để cookie set được
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path=COOKIE_PATH, httponly=True, samesite="strict"
    )
