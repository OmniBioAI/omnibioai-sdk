"""omnibioai/auth/tokens.py"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenPair:
    """Holds the SDK's current access/refresh tokens. Mutated in place by
    AuthenticatedSession on a successful refresh (see auth/session.py), so
    every service sub-client sharing the same TokenPair instance -- via
    the parent OmniBioAI client -- sees a refreshed access_token on its
    very next request. There is exactly one TokenPair per OmniBioAI
    instance; it is never copied per sub-client."""

    access_token: str
    refresh_token: Optional[str] = None

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}
