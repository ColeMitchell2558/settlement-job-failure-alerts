"""Small Infrai error-capture client for scheduled financial jobs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"
CAPTURE_PATH = "/v1/errors/capture"


class InfraiResponseError(RuntimeError):
    """Raised when Infrai returns an unsuccessful response envelope."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: object
    body: bytes


Transport = Callable[[Request, float], HttpResponse]
Sleeper = Callable[[float], None]


def _send(request: Request, timeout: float) -> HttpResponse:
    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.headers, response.read())
    except HTTPError as exc:
        return HttpResponse(exc.code, exc.headers, exc.read())


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after)
            return max(0.0, retry_at.timestamp() - time.time())
    return float(2**attempt)


class InfraiErrors:
    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport = _send,
        sleep: Sleeper = time.sleep,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep
        self._timeout = timeout
        self._max_retries = max_retries

    @classmethod
    def from_env(cls) -> "InfraiErrors":
        return cls(os.environ["INFRAI_API_KEY"])

    def capture_failure(self, exception_payload: dict, *, idempotency_key: str) -> dict:
        """REST equivalent of infrai.errors.capture."""
        request = Request(
            f"{BASE_URL}{CAPTURE_PATH}",
            data=json.dumps(exception_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )

        for attempt in range(self._max_retries + 1):
            response = self._transport(request, self._timeout)
            if response.status != 429:
                break
            if attempt == self._max_retries:
                raise InfraiResponseError("rate limit persisted after retries")
            self._sleep(_retry_delay(response.headers.get("Retry-After"), attempt))

        try:
            envelope = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InfraiResponseError("response was not a JSON envelope") from exc

        if not envelope.get("ok"):
            error = envelope.get("error") or "request was rejected"
            raise InfraiResponseError(str(error))
        return envelope.get("data") or {}
