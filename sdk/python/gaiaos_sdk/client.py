"""High-level client interfaces for GaiaOS API interaction."""

from __future__ import annotations

import os
import warnings
from collections.abc import AsyncGenerator, Generator
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from gaiaos_sdk import __version__
from gaiaos_sdk._generated.api.v1 import (
    create_api_key_api_v1_api_keys_post,
    create_investigation_api_v1_investigations_post,
    get_investigation_api_v1_investigations_investigation_id_get,
    get_investigation_trace_api_v1_investigations_investigation_id_trace_get,
    list_api_keys_api_v1_api_keys_get,
    list_public_hazard_events_api_v1_research_hazard_events_get,
    list_public_research_investigations_api_v1_research_investigations_get,
    list_public_research_patterns_api_v1_research_patterns_get,
    liveness_api_v1_health_live_get,
    login_api_v1_auth_login_post,
    register_api_v1_auth_register_post,
    revoke_api_key_api_v1_api_keys_key_id_delete,
)
from gaiaos_sdk._generated.client import AuthenticatedClient, Client
from gaiaos_sdk._generated.models import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    HazardEventResponse,
    InvestigationCreateRequest,
    InvestigationCreateResponse,
    InvestigationStatusResponse,
    InvestigationTraceResponse,
    PatternFindingResponse,
    ResearchInvestigationResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from gaiaos_sdk.exceptions import (
    GaiaAPIError,
    IncompatibleServerError,
    raise_for_status,
)
from gaiaos_sdk.streaming import (
    StreamEvent,
    astream_investigation_events,
    stream_investigation_events,
)

DEFAULT_BASE_URL = "http://localhost:8000"


def _check_version_compatibility(server_ver_str: str) -> None:
    """Validate server version string against SDK version using semantic versioning."""
    try:
        server_v = Version(server_ver_str)
        sdk_v = Version(__version__)
        if server_v.major != sdk_v.major:
            msg = f"Server ({server_ver_str}) major version incompatible with SDK ({__version__})"
            raise IncompatibleServerError(msg)
        if server_v.minor != sdk_v.minor:
            msg = f"GaiaOS server ({server_ver_str}) minor release differs from SDK ({__version__})"
            warnings.warn(msg, UserWarning, stacklevel=3)
    except InvalidVersion as err:
        server_major = server_ver_str.split(".")[0]
        sdk_major = __version__.split(".")[0]
        if server_major != sdk_major:
            msg = f"Server ({server_ver_str}) major version incompatible with SDK ({__version__})"
            raise IncompatibleServerError(msg) from err


class InvestigationsClient:
    """Synchronous interface for GaiaOS investigation queries and traces."""

    def __init__(self, parent: GaiaClient) -> None:
        self._parent = parent

    def create(
        self, query: str, consent_public_research: bool = False
    ) -> InvestigationCreateResponse:
        """Submit a new planetary risk investigation."""
        client = self._parent._get_gen_client()
        body = InvestigationCreateRequest(
            query=query, consent_public_research=consent_public_research
        )
        resp = create_investigation_api_v1_investigations_post.sync_detailed(
            client=client, body=body
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationCreateResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def get(self, investigation_id: str) -> InvestigationStatusResponse:
        """Fetch status and findings for an investigation."""
        client = self._parent._get_gen_client()
        resp = get_investigation_api_v1_investigations_investigation_id_get.sync_detailed(
            investigation_id, client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationStatusResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def get_trace(self, investigation_id: str) -> InvestigationTraceResponse:
        """Fetch full execution trace node/edge graph for an investigation (Milestone 1)."""
        client = self._parent._get_gen_client()
        fn = get_investigation_trace_api_v1_investigations_investigation_id_trace_get
        resp = fn.sync_detailed(investigation_id, client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationTraceResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def stream(self, investigation_id: str) -> Generator[StreamEvent, None, None]:
        """Stream real-time SSE execution events for an investigation trace."""
        url = f"{self._parent.base_url}/api/v1/investigations/{investigation_id}/stream"
        headers = self._parent._get_headers()
        yield from stream_investigation_events(
            self._parent._httpx_client, url, headers=headers
        )


class AsyncInvestigationsClient:
    """Asynchronous interface for GaiaOS investigation queries and traces."""

    def __init__(self, parent: AsyncGaiaClient) -> None:
        self._parent = parent

    async def create(
        self, query: str, consent_public_research: bool = False
    ) -> InvestigationCreateResponse:
        """Submit a new planetary risk investigation asynchronously."""
        client = self._parent._get_gen_client()
        body = InvestigationCreateRequest(
            query=query, consent_public_research=consent_public_research
        )
        resp = await create_investigation_api_v1_investigations_post.asyncio_detailed(
            client=client, body=body
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationCreateResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def get(self, investigation_id: str) -> InvestigationStatusResponse:
        """Fetch status and findings for an investigation asynchronously."""
        client = self._parent._get_gen_client()
        resp = await get_investigation_api_v1_investigations_investigation_id_get.asyncio_detailed(
            investigation_id, client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationStatusResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def get_trace(self, investigation_id: str) -> InvestigationTraceResponse:
        """Fetch full execution trace node/edge graph for an investigation (Milestone 1)."""
        client = self._parent._get_gen_client()
        fn = get_investigation_trace_api_v1_investigations_investigation_id_trace_get
        resp = await fn.asyncio_detailed(investigation_id, client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, InvestigationTraceResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def stream(self, investigation_id: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream real-time SSE execution events for an investigation trace asynchronously."""
        url = f"{self._parent.base_url}/api/v1/investigations/{investigation_id}/stream"
        headers = self._parent._get_headers()
        async for event in astream_investigation_events(
            self._parent._httpx_client, url, headers=headers
        ):
            yield event


class AuthClient:
    """Synchronous interface for authentication and API key management."""

    def __init__(self, parent: GaiaClient) -> None:
        self._parent = parent

    def login(self, username: str, password: str) -> TokenResponse:
        """Authenticate user credentials and retrieve a Bearer JWT token."""
        client = self._parent._get_gen_client()
        body = UserLoginRequest(username=username, password=password)
        resp = login_api_v1_auth_login_post.sync_detailed(client=client, body=body)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, TokenResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def register(
        self, email: str, password: str, full_name: str | None = None
    ) -> UserResponse:
        """Register a new user account."""
        client = self._parent._get_gen_client()
        body = UserRegisterRequest(email=email, password=password, full_name=full_name)
        resp = register_api_v1_auth_register_post.sync_detailed(client=client, body=body)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, UserResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def create_api_key(
        self, name: str, expires_in_days: int | None = None
    ) -> ApiKeyCreatedResponse:
        """Generate a new API key."""
        client = self._parent._get_gen_client()
        body = CreateApiKeyRequest(name=name, expires_in_days=expires_in_days)
        resp = create_api_key_api_v1_api_keys_post.sync_detailed(client=client, body=body)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, ApiKeyCreatedResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def list_api_keys(self) -> list[ApiKeyResponse]:
        """List active API keys for the current account."""
        client = self._parent._get_gen_client()
        resp = list_api_keys_api_v1_api_keys_get.sync_detailed(client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def revoke_api_key(self, key_id: str) -> None:
        """Revoke an existing API key."""
        client = self._parent._get_gen_client()
        resp = revoke_api_key_api_v1_api_keys_key_id_delete.sync_detailed(
            key_id, client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)


class AsyncAuthClient:
    """Asynchronous interface for authentication and API key management."""

    def __init__(self, parent: AsyncGaiaClient) -> None:
        self._parent = parent

    async def login(self, username: str, password: str) -> TokenResponse:
        """Authenticate user credentials and retrieve a Bearer JWT token asynchronously."""
        client = self._parent._get_gen_client()
        body = UserLoginRequest(username=username, password=password)
        resp = await login_api_v1_auth_login_post.asyncio_detailed(client=client, body=body)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, TokenResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def register(
        self, email: str, password: str, full_name: str | None = None
    ) -> UserResponse:
        """Register a new user account asynchronously."""
        client = self._parent._get_gen_client()
        body = UserRegisterRequest(email=email, password=password, full_name=full_name)
        resp = await register_api_v1_auth_register_post.asyncio_detailed(
            client=client, body=body
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, UserResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def create_api_key(
        self, name: str, expires_in_days: int | None = None
    ) -> ApiKeyCreatedResponse:
        """Generate a new API key asynchronously."""
        client = self._parent._get_gen_client()
        body = CreateApiKeyRequest(name=name, expires_in_days=expires_in_days)
        resp = await create_api_key_api_v1_api_keys_post.asyncio_detailed(
            client=client, body=body
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, ApiKeyCreatedResponse):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def list_api_keys(self) -> list[ApiKeyResponse]:
        """List active API keys for the current account asynchronously."""
        client = self._parent._get_gen_client()
        resp = await list_api_keys_api_v1_api_keys_get.asyncio_detailed(client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def revoke_api_key(self, key_id: str) -> None:
        """Revoke an existing API key asynchronously."""
        client = self._parent._get_gen_client()
        resp = await revoke_api_key_api_v1_api_keys_key_id_delete.asyncio_detailed(
            key_id, client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)


class ResearchClient:
    """Synchronous interface for public research endpoints and pattern mining."""

    def __init__(self, parent: GaiaClient) -> None:
        self._parent = parent

    def list_patterns(self) -> list[PatternFindingResponse]:
        """List longitudinal recurring risk patterns (Milestone 2)."""
        client = self._parent._get_gen_client()
        resp = list_public_research_patterns_api_v1_research_patterns_get.sync_detailed(
            client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def list_hazard_events(self) -> list[HazardEventResponse]:
        """List historical multi-source hazard events."""
        client = self._parent._get_gen_client()
        resp = list_public_hazard_events_api_v1_research_hazard_events_get.sync_detailed(
            client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    def list_investigations(self) -> list[ResearchInvestigationResponse]:
        """List anonymized public research investigations."""
        client = self._parent._get_gen_client()
        fn = list_public_research_investigations_api_v1_research_investigations_get
        resp = fn.sync_detailed(client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")


class AsyncResearchClient:
    """Asynchronous interface for public research endpoints and pattern mining."""

    def __init__(self, parent: AsyncGaiaClient) -> None:
        self._parent = parent

    async def list_patterns(self) -> list[PatternFindingResponse]:
        """List longitudinal recurring risk patterns (Milestone 2) asynchronously."""
        client = self._parent._get_gen_client()
        resp = await list_public_research_patterns_api_v1_research_patterns_get.asyncio_detailed(
            client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def list_hazard_events(self) -> list[HazardEventResponse]:
        """List historical multi-source hazard events asynchronously."""
        client = self._parent._get_gen_client()
        resp = await list_public_hazard_events_api_v1_research_hazard_events_get.asyncio_detailed(
            client=client
        )
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")

    async def list_investigations(self) -> list[ResearchInvestigationResponse]:
        """List anonymized public research investigations asynchronously."""
        client = self._parent._get_gen_client()
        fn = list_public_research_investigations_api_v1_research_investigations_get
        resp = await fn.asyncio_detailed(client=client)
        raise_for_status(resp.status_code, resp.content, resp.headers)
        if isinstance(resp.parsed, list):
            return resp.parsed
        raise GaiaAPIError(resp.status_code, "Unexpected response payload type")


class GaiaClient:
    """Main synchronous client entry point for GaiaOS."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        bearer_token: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """Initialize synchronous GaiaOS client.

        Args:
            base_url: Server API base URL (defaults to GAIAOS_API_URL or http://localhost:8000).
            api_key: API key authentication token (defaults to GAIAOS_API_KEY).
            bearer_token: JWT bearer token (defaults to GAIAOS_BEARER_TOKEN).
            timeout: Request timeout in seconds.
            max_retries: Number of HTTP transport-level retries for network drops/timeouts.
        """
        self.base_url = (
            base_url
            or os.environ.get("GAIAOS_API_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("GAIAOS_API_KEY")
        self.bearer_token = bearer_token or os.environ.get("GAIAOS_BEARER_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries

        transport = httpx.HTTPTransport(retries=self.max_retries)
        self._httpx_client = httpx.Client(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=self.timeout,
            transport=transport,
        )

        self.investigations = InvestigationsClient(self)
        self.auth = AuthClient(self)
        self.research = ResearchClient(self)

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": f"gaiaos-sdk-python/{__version__}"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _get_gen_client(self) -> AuthenticatedClient | Client:
        token = self.bearer_token or self.api_key or ""
        if token:
            return AuthenticatedClient(
                base_url=self.base_url,
                token=token,
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout),
            )
        return Client(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=httpx.Timeout(self.timeout),
        )

    def validate_server(self) -> dict[str, Any]:
        """Validate server compatibility against SDK version (Milestone 3 opt-in validation)."""
        gen_client = self._get_gen_client()
        resp = liveness_api_v1_health_live_get.sync_detailed(client=gen_client)
        raise_for_status(resp.status_code, resp.content, resp.headers)

        if not resp.parsed or not hasattr(resp.parsed, "app_version"):
            raise IncompatibleServerError("Unable to determine GaiaOS server version")

        server_ver = str(resp.parsed.app_version)
        _check_version_compatibility(server_ver)
        return {"status": "ok", "server_version": server_ver, "sdk_version": __version__}

    def close(self) -> None:
        """Close the underlying HTTP client transport."""
        self._httpx_client.close()

    def __enter__(self) -> GaiaClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class AsyncGaiaClient:
    """Main asynchronous client entry point for GaiaOS."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        bearer_token: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """Initialize asynchronous GaiaOS client.

        Args:
            base_url: Server API base URL (defaults to GAIAOS_API_URL or http://localhost:8000).
            api_key: API key authentication token (defaults to GAIAOS_API_KEY).
            bearer_token: JWT bearer token (defaults to GAIAOS_BEARER_TOKEN).
            timeout: Request timeout in seconds.
            max_retries: Number of HTTP transport-level retries for network drops/timeouts.
        """
        self.base_url = (
            base_url
            or os.environ.get("GAIAOS_API_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("GAIAOS_API_KEY")
        self.bearer_token = bearer_token or os.environ.get("GAIAOS_BEARER_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries

        transport = httpx.AsyncHTTPTransport(retries=self.max_retries)
        self._httpx_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=self.timeout,
            transport=transport,
        )

        self.investigations = AsyncInvestigationsClient(self)
        self.auth = AsyncAuthClient(self)
        self.research = AsyncResearchClient(self)

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": f"gaiaos-sdk-python/{__version__}"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _get_gen_client(self) -> AuthenticatedClient | Client:
        token = self.bearer_token or self.api_key or ""
        if token:
            return AuthenticatedClient(
                base_url=self.base_url,
                token=token,
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout),
            )
        return Client(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=httpx.Timeout(self.timeout),
        )

    async def validate_server(self) -> dict[str, Any]:
        """Validate server compatibility against SDK version asynchronously."""
        gen_client = self._get_gen_client()
        resp = await liveness_api_v1_health_live_get.asyncio_detailed(client=gen_client)
        raise_for_status(resp.status_code, resp.content, resp.headers)

        if not resp.parsed or not hasattr(resp.parsed, "app_version"):
            raise IncompatibleServerError("Unable to determine GaiaOS server version")

        server_ver = str(resp.parsed.app_version)
        _check_version_compatibility(server_ver)
        return {"status": "ok", "server_version": server_ver, "sdk_version": __version__}

    async def aclose(self) -> None:
        """Close the underlying async HTTP client transport."""
        await self._httpx_client.aclose()

    async def __aenter__(self) -> AsyncGaiaClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()
