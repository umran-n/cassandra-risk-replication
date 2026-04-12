from __future__ import annotations

from typing import Any

import requests

from .exceptions import AuthError, CassandraAPIError, RateLimitError
from .models import FamilySignal, HealthResponse, RegistryEntry, RSIResponse, SignalContract, SourceStatus, ThemeSignal


class CassandraClient:
    BASE_URL = "https://cassandra-risk.up.railway.app"

    def __init__(
        self,
        api_key: str = None,
        enterprise_key: str = None,
        base_url: str = None,
        timeout: int = 10,
    ):
        self.api_key = api_key
        self.enterprise_key = enterprise_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self, *, enterprise: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if enterprise and self.enterprise_key:
            headers["X-Enterprise-Key"] = self.enterprise_key
        return headers

    def _extract_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "Request failed"
        if isinstance(payload, dict):
            if payload.get("message"):
                return str(payload["message"])
            if payload.get("error"):
                return str(payload["error"])
        return response.text or "Request failed"

    def _get(self, path, params=None, *, enterprise: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, params=params, headers=self._headers(enterprise=enterprise), timeout=self.timeout)
        except requests.Timeout as exc:
            raise CassandraAPIError(408, "Request timed out") from exc
        except requests.RequestException as exc:
            raise CassandraAPIError(0, str(exc)) from exc

        if response.status_code in (401, 403):
            raise AuthError(response.status_code, self._extract_message(response))
        if response.status_code == 429:
            raise RateLimitError(
                response.status_code,
                self._extract_message(response),
                retry_after=response.headers.get("Retry-After"),
            )
        if response.status_code >= 500:
            raise CassandraAPIError(response.status_code, self._extract_message(response))
        if response.status_code >= 400:
            raise CassandraAPIError(response.status_code, self._extract_message(response))
        return response.json()

    def _require_enterprise(self):
        if not self.enterprise_key:
            raise AuthError(403, "Enterprise access requires enterprise_key")

    def health(self) -> HealthResponse:
        return HealthResponse.from_dict(self._get("/health"))

    def meta(self) -> dict:
        return self._get("/v1/meta")

    def rsi_latest(self) -> RSIResponse:
        return RSIResponse.from_dict(self._get("/v1/rsi/latest"))

    def signals_latest(self) -> list[SignalContract]:
        payload = self._get("/v1/signals/latest")
        return [SignalContract.from_dict(item) for item in payload]

    def signal_by_family(self, family_id: str) -> SignalContract:
        return SignalContract.from_dict(self._get(f"/v1/signals/latest/{family_id}"))

    def registry_governed(self) -> list[RegistryEntry]:
        payload = self._get("/v1/registry/governed")
        families = payload.get("families", payload) if isinstance(payload, dict) else payload
        return [RegistryEntry.from_dict(item) for item in families]

    def sources_status(self) -> list[SourceStatus]:
        payload = self._get("/v1/sources/status")
        return [SourceStatus.from_dict(item) for item in payload]

    def rsi_history(self, days: int = 30) -> list[RSIResponse]:
        self._require_enterprise()
        payload = self._get("/v1/enterprise/rsi/history", params={"limit": days}, enterprise=True)
        return [RSIResponse.from_dict(item) for item in payload]

    def themes_latest(self) -> list[ThemeSignal]:
        self._require_enterprise()
        payload = self._get("/v1/enterprise/themes/latest", enterprise=True)
        return [ThemeSignal.from_dict(item) for item in payload]

    def themes_history(self, days: int = 30) -> list[ThemeSignal]:
        self._require_enterprise()
        payload = self._get("/v1/enterprise/themes/history", params={"limit": days}, enterprise=True)
        return [ThemeSignal.from_dict(item) for item in payload]

    def families_latest(self) -> list[FamilySignal]:
        self._require_enterprise()
        payload = self._get("/v1/enterprise/families/latest", enterprise=True)
        return [FamilySignal.from_dict(item) for item in payload]
