"""omnibioai/client.py"""
from __future__ import annotations

from typing import Optional

from .auth.session import AuthenticatedSession
from .auth.tokens import TokenPair
from .rag.client import RAGClient

# No public API Gateway URL is documented anywhere in this ecosystem yet
# (Phase 1 findings, Open Question #2) -- defaults to the gateway's own
# local dev port (see omnibioai-api-gateway's Dockerfile: EXPOSE 8080) for
# a working zero-config local experience, matching the pattern the
# pre-existing OmniClient already used for its own (different) backend.
# Any non-local deployment must override this explicitly.
DEFAULT_BASE_URL = "http://127.0.0.1:8080"

# Matches omnibioai-control-center's own JWKS_URL default
# ("https://auth.omnibioai.org/.well-known/jwks.json") -- the one
# documented public convention for reaching omnibioai-auth directly that
# exists in this ecosystem today. Login/refresh/logout are NOT reachable
# through the API Gateway's SERVICE_MAP (it has no "auth" entry -- see
# Phase 1 findings), so this is deliberately a *separate* URL from
# base_url, not a path under it.
DEFAULT_AUTH_URL = "https://auth.omnibioai.org"


class OmniBioAI:
    """Top-level SDK client. Holds one shared AuthenticatedSession (one
    token pair, one requests.Session, one refresh-on-401 policy) that
    every service sub-client is constructed against -- so a token refresh
    triggered by any one of them is immediately visible to all the
    others, and there is exactly one connection pool for the whole
    client.

    .models / .workflows sub-clients ship in later PRs (SDK Phase 2
    PR3/PR4) once each one's own scope is confirmed (workflows is
    explicitly blocked on a TES-vs-workflow-bundles decision -- see the
    Phase 1 findings report's Open Questions). Until then, `client.models`/
    `client.workflows` raise a normal AttributeError rather than
    something confusing, since this constructor deliberately does not
    stub them out as empty placeholders. `.rag` is available now (PR2).

    Does not verify or decode access_token/refresh_token, and does not
    depend on omnibioai-iam-client -- see the Phase 1 findings report's
    Authentication Design section for why: IAM verification is the API
    Gateway's and each service's responsibility, not this SDK's.
    """

    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        auth_url: str = DEFAULT_AUTH_URL,
        timeout: float = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.tokens = TokenPair(access_token=access_token, refresh_token=refresh_token)
        self.session = AuthenticatedSession(
            tokens=self.tokens, auth_url=auth_url, timeout=timeout,
        )
        self.rag = RAGClient(base_url=f"{self.base_url}/rag", session=self.session)

    @property
    def access_token(self) -> str:
        """Current access token -- reflects any in-place refresh
        AuthenticatedSession has performed, not necessarily the value
        originally passed to __init__."""
        return self.tokens.access_token

    @property
    def refresh_token(self) -> Optional[str]:
        """Current refresh token -- omnibioai-auth's refresh tokens are
        single-use and rotated on every successful refresh, so this may
        differ from the value originally passed to __init__ after the
        first automatic refresh."""
        return self.tokens.refresh_token
