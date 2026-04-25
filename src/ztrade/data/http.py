from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpClientError(RuntimeError):
    pass


class JsonHttpClient:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    def get_json(
        self,
        url: str,
        params: dict[str, str | int | float | bool | None] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        request_url = f"{url}?{urlencode(query)}" if query else url
        request = Request(request_url, headers=headers or {})
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise HttpClientError(f"HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise HttpClientError(f"Network error for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise HttpClientError(f"Invalid JSON from {url}") from exc
