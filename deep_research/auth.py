from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status


@dataclass(frozen=True)
class ClerkUser:
    external_auth_id: str
    email: str | None
    name: str | None


def get_clerk_secret_key() -> str:
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("CLERK_SECRET_KEY must be set.")
    return secret_key


async def fetch_clerk_user(user_id: str) -> ClerkUser:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.clerk.com/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {get_clerk_secret_key()}"},
        )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk user was not found.",
        )

    response.raise_for_status()
    payload = response.json()

    return ClerkUser(
        external_auth_id=payload["id"],
        email=get_primary_email(payload),
        name=get_display_name(payload),
    )


def get_primary_email(payload: dict[str, Any]) -> str | None:
    primary_email_id = payload.get("primary_email_address_id")

    for email in payload.get("email_addresses", []):
        if email.get("id") == primary_email_id:
            return email.get("email_address")

    email_addresses = payload.get("email_addresses") or []
    if email_addresses:
        return email_addresses[0].get("email_address")

    return None


def get_display_name(payload: dict[str, Any]) -> str | None:
    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    name = " ".join(part for part in [first_name, last_name] if part)

    if name:
        return name

    return payload.get("username")
