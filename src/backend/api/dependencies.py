from __future__ import annotations

from typing import Annotated

from fastapi import Header

from ..config_loader import get_settings
from ..services.errors import AuthError


async def verify_api_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected_token = get_settings().security.api_token
    if not authorization:
        raise AuthError(
            "Missing Authorization header",
            status_code=401,
        )

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise AuthError(
            "Invalid authorization scheme",
            status_code=401,
        )

    received_token = authorization[len(prefix) :].strip()
    if received_token != expected_token:
        raise AuthError(
            "Invalid API token",
            status_code=403,
        )
