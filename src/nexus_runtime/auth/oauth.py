from __future__ import annotations

import base64
from dataclasses import dataclass, replace
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import re
import secrets
import ssl
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
import webbrowser

from .types import (
    AuthProtocolError,
    AuthTimeoutError,
    AuthUnavailableError,
    BrowserOAuthConfig,
    DeviceOAuthConfig,
    SecretMaterial,
)


MAX_OAUTH_RESPONSE_BYTES = 65_536
MAX_INVALID_CALLBACKS = 8
MAX_DEVICE_AUTHORIZATION_SECONDS = 1_800.0
_OAUTH_ERROR = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def _safe_visible_ascii(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and all(0x21 <= ord(character) <= 0x7E for character in value)
    )


class _TokenConfig(Protocol):
    token_endpoint: str
    client_id: str
    allowed_endpoint_hosts: tuple[str, ...]
    allow_insecure_loopback_provider: bool


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class OAuthEndpointError(AuthProtocolError):
    def __init__(self, error_code: str) -> None:
        safe_code = error_code if _OAUTH_ERROR.fullmatch(error_code) else "provider_error"
        self.error_code = safe_code
        super().__init__(f"OAuth provider returned {safe_code}")


def _read_bounded(stream: Any) -> bytes:
    payload = stream.read(MAX_OAUTH_RESPONSE_BYTES + 1)
    if len(payload) > MAX_OAUTH_RESPONSE_BYTES:
        raise AuthProtocolError("OAuth provider response exceeded the size limit")
    return payload


def _parse_json_object(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthProtocolError("OAuth provider returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise AuthProtocolError("OAuth provider response must be an object")
    return value


def _safe_oauth_error(payload: bytes) -> OAuthEndpointError:
    try:
        value = _parse_json_object(payload)
        error = value.get("error")
    except AuthProtocolError:
        error = None
    return OAuthEndpointError(error if isinstance(error, str) else "provider_error")


def _endpoint_host_is_admitted(url: str, config: _TokenConfig) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host not in {item.lower() for item in config.allowed_endpoint_hosts}:
        return False
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "https":
        return True
    return (
        config.allow_insecure_loopback_provider
        and parsed.scheme == "http"
        and host in {"127.0.0.1", "::1"}
    )


class OAuthHTTPClient:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("OAuth HTTP timeout must be positive and finite")
        self.timeout_seconds = timeout_seconds

    def post_form(self, endpoint: str, form: Mapping[str, str], config: _TokenConfig) -> dict[str, Any]:
        if not _endpoint_host_is_admitted(endpoint, config):
            raise AuthProtocolError("OAuth request destination is not admitted by the adapter descriptor")
        request = Request(
            endpoint,
            data=urlencode(form).encode("ascii"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "qsol-nexus-auth/1",
            },
            method="POST",
        )
        handlers: list[Any] = [_RejectRedirects(), HTTPSHandler(context=ssl.create_default_context())]
        if config.allow_insecure_loopback_provider:
            handlers.insert(0, ProxyHandler({}))
        opener = build_opener(*handlers)
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                return _parse_json_object(_read_bounded(response))
        except HTTPError as exc:
            payload = _read_bounded(exc)
            raise _safe_oauth_error(payload) from None
        except (TimeoutError, URLError, OSError) as exc:
            raise AuthUnavailableError("OAuth provider request failed") from exc


def parse_token_response(payload: Mapping[str, Any], *, now: float) -> SecretMaterial:
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    token_type = payload.get("token_type", "Bearer")
    expires_in = payload.get("expires_in")
    raw_scope = payload.get("scope", "")
    if expires_in is None:
        expires_at = None
    elif isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
        raise AuthProtocolError("OAuth expires_in must be numeric")
    elif not math.isfinite(float(expires_in)) or expires_in <= 0:
        raise AuthProtocolError("OAuth expires_in must be positive and finite")
    else:
        expires_at = now + float(expires_in)
    if isinstance(raw_scope, str):
        scopes = tuple(item for item in raw_scope.split() if item)
    elif isinstance(raw_scope, list) and all(isinstance(item, str) and item for item in raw_scope):
        scopes = tuple(raw_scope)
    else:
        raise AuthProtocolError("OAuth scope is invalid")
    return SecretMaterial(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        expires_at=expires_at,
        scopes=scopes,
    )


class OAuthTokenClient:
    def __init__(self, http: OAuthHTTPClient | None = None, *, clock: Callable[[], float] = time.time) -> None:
        self.http = http or OAuthHTTPClient()
        self.clock = clock

    def exchange_authorization_code(
        self,
        config: BrowserOAuthConfig,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> SecretMaterial:
        payload = self.http.post_form(
            config.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config.client_id,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            },
            config,
        )
        return parse_token_response(payload, now=self.clock())

    def refresh(self, config: _TokenConfig, material: SecretMaterial) -> SecretMaterial:
        if material.refresh_token is None:
            raise AuthUnavailableError("credential expired and has no refresh token")
        payload = self.http.post_form(
            config.token_endpoint,
            {
                "grant_type": "refresh_token",
                "refresh_token": material.refresh_token,
                "client_id": config.client_id,
            },
            config,
        )
        refreshed = parse_token_response(payload, now=self.clock())
        if refreshed.refresh_token is None:
            refreshed = replace(refreshed, refresh_token=material.refresh_token)
        return refreshed


def _pkce_verifier() -> str:
    # token_urlsafe(64) is within RFC 7636's 43-128 character verifier range.
    verifier = secrets.token_urlsafe(64)
    if not 43 <= len(verifier) <= 128:
        raise RuntimeError("generated PKCE verifier length is invalid")
    return verifier


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class _CallbackState:
    expected_state: str
    code: str | None = None
    error: AuthProtocolError | None = None
    invalid_callbacks: int = 0


def _callback_handler(state: _CallbackState, callback_path: str) -> type[BaseHTTPRequestHandler]:
    class CallbackHandler(BaseHTTPRequestHandler):
        server_version = "NexusAuthCallback/1"

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != callback_path:
                self._respond(404, "This is not the NEXUS authorization callback.")
                return
            try:
                pairs = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=16)
            except ValueError:
                state.invalid_callbacks += 1
                self._respond(400, "Authorization callback was rejected.")
                return
            values: dict[str, list[str]] = {}
            for key, value in pairs:
                values.setdefault(key, []).append(value)
            if any(len(items) != 1 for items in values.values()):
                state.invalid_callbacks += 1
                self._respond(400, "Authorization callback was rejected.")
                return
            received_state = values.get("state", [""])[0]
            if not secrets.compare_digest(received_state, state.expected_state):
                state.invalid_callbacks += 1
                self._respond(400, "Authorization callback state did not match.")
                return
            provider_error = values.get("error", [None])[0]
            if provider_error is not None:
                state.error = OAuthEndpointError(provider_error)
                self._respond(400, "Authorization was not granted. Return to NEXUS.")
                return
            code = values.get("code", [None])[0]
            if not isinstance(code, str) or not code or len(code) > 4096:
                state.invalid_callbacks += 1
                self._respond(400, "Authorization callback did not contain a valid code.")
                return
            state.code = code
            self._respond(200, "Authorization complete. You may close this tab and return to NEXUS.")

        def _respond(self, status: int, message: str) -> None:
            body = (
                "<!doctype html><meta charset=utf-8><title>NEXUS authorization</title>"
                f"<p>{message}</p>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    return CallbackHandler


class BrowserPKCEFlow:
    def __init__(
        self,
        token_client: OAuthTokenClient | None = None,
        *,
        browser_open: Callable[[str], bool] = webbrowser.open,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.token_client = token_client or OAuthTokenClient()
        self.browser_open = browser_open
        self.monotonic = monotonic

    def authorize(
        self,
        config: BrowserOAuthConfig,
        *,
        open_browser: bool = True,
        on_authorization_url: Callable[[str], None] | None = None,
    ) -> SecretMaterial:
        verifier = _pkce_verifier()
        state_token = secrets.token_urlsafe(32)
        callback_path = "/oauth/callback"
        callback_state = _CallbackState(expected_state=state_token)
        server = HTTPServer(("127.0.0.1", 0), _callback_handler(callback_state, callback_path))
        server.timeout = 0.25
        redirect_uri = f"http://127.0.0.1:{server.server_port}{callback_path}"
        parameters: list[tuple[str, str]] = [
            ("response_type", "code"),
            ("client_id", config.client_id),
            ("redirect_uri", redirect_uri),
            ("scope", " ".join(config.scopes)),
            ("state", state_token),
            ("code_challenge", _pkce_challenge(verifier)),
            ("code_challenge_method", "S256"),
            *config.extra_authorization_params,
        ]
        parsed_endpoint = urlsplit(config.authorization_endpoint)
        authorization_url = urlunsplit(
            (parsed_endpoint.scheme, parsed_endpoint.netloc, parsed_endpoint.path, urlencode(parameters), "")
        )
        deadline = self.monotonic() + config.callback_timeout_seconds
        try:
            if on_authorization_url is not None:
                on_authorization_url(authorization_url)
            if open_browser:
                try:
                    self.browser_open(authorization_url)
                except (OSError, webbrowser.Error):
                    pass
            while callback_state.code is None and callback_state.error is None:
                if callback_state.invalid_callbacks >= MAX_INVALID_CALLBACKS:
                    raise AuthProtocolError("too many invalid authorization callbacks")
                if self.monotonic() >= deadline:
                    raise AuthTimeoutError("browser authorization timed out")
                server.handle_request()
        finally:
            server.server_close()
        if callback_state.error is not None:
            raise callback_state.error
        if callback_state.code is None:
            raise AuthProtocolError("browser authorization ended without a code")
        return self.token_client.exchange_authorization_code(
            config,
            code=callback_state.code,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
        )


@dataclass(frozen=True, repr=False)
class DeviceAuthorizationPrompt:
    verification_uri: str
    verification_uri_complete: str | None
    user_code: str = ""

    def __repr__(self) -> str:
        return "DeviceAuthorizationPrompt(verification_uri=<redacted>, user_code=<redacted>)"

    def public_dict(self) -> dict[str, str | None]:
        return {
            "verification_uri": self.verification_uri,
            "verification_uri_complete": self.verification_uri_complete,
            "user_code": self.user_code,
        }


class DeviceCodeFlow:
    def __init__(
        self,
        http: OAuthHTTPClient | None = None,
        *,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http or OAuthHTTPClient()
        self.clock = clock
        self.monotonic = monotonic
        self.sleep = sleep

    def authorize(
        self,
        config: DeviceOAuthConfig,
        *,
        on_prompt: Callable[[DeviceAuthorizationPrompt], None],
    ) -> SecretMaterial:
        started = self.http.post_form(
            config.device_authorization_endpoint,
            {"client_id": config.client_id, "scope": " ".join(config.scopes)},
            config,
        )
        device_code = started.get("device_code")
        user_code = started.get("user_code")
        verification_uri = started.get("verification_uri")
        verification_uri_complete = started.get("verification_uri_complete")
        expires_in = started.get("expires_in")
        interval = started.get("interval", 5)
        if not _safe_visible_ascii(device_code, maximum=4096):
            raise AuthProtocolError("device authorization response has no valid device code")
        if not _safe_visible_ascii(user_code, maximum=256):
            raise AuthProtocolError("device authorization response has no valid user code")
        if not _safe_visible_ascii(verification_uri, maximum=4096) or not self._verification_url_is_admitted(
            verification_uri,
            config,
        ):
            raise AuthProtocolError("device verification URL is not admitted by the adapter descriptor")
        if verification_uri_complete is not None and (
            not _safe_visible_ascii(verification_uri_complete, maximum=4096)
            or not self._verification_url_is_admitted(verification_uri_complete, config)
        ):
            raise AuthProtocolError("complete device verification URL is not admitted by the adapter descriptor")
        if (
            isinstance(expires_in, bool)
            or not isinstance(expires_in, (int, float))
            or not math.isfinite(float(expires_in))
            or expires_in <= 0
        ):
            raise AuthProtocolError("device authorization expiry is invalid")
        if (
            isinstance(interval, bool)
            or not isinstance(interval, (int, float))
            or not math.isfinite(float(interval))
            or interval <= 0
        ):
            raise AuthProtocolError("device authorization polling interval is invalid")
        prompt = DeviceAuthorizationPrompt(verification_uri, verification_uri_complete, user_code)
        on_prompt(prompt)

        deadline = self.monotonic() + min(float(expires_in), MAX_DEVICE_AUTHORIZATION_SECONDS)
        polling_interval = max(float(interval), 1.0)
        while self.monotonic() < deadline:
            self.sleep(min(polling_interval, max(0.0, deadline - self.monotonic())))
            if self.monotonic() >= deadline:
                break
            try:
                payload = self.http.post_form(
                    config.token_endpoint,
                    {
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": device_code,
                        "client_id": config.client_id,
                    },
                    config,
                )
            except OAuthEndpointError as exc:
                if exc.error_code == "authorization_pending":
                    continue
                if exc.error_code == "slow_down":
                    polling_interval += 5.0
                    continue
                if exc.error_code == "expired_token":
                    raise AuthTimeoutError("device authorization expired") from None
                raise
            return parse_token_response(payload, now=self.clock())
        raise AuthTimeoutError("device authorization timed out")

    @staticmethod
    def _verification_url_is_admitted(url: str, config: DeviceOAuthConfig) -> bool:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            return False
        if host not in {item.lower() for item in config.allowed_verification_hosts}:
            return False
        if parsed.scheme == "https":
            return True
        return (
            config.allow_insecure_loopback_provider
            and parsed.scheme == "http"
            and host in {"127.0.0.1", "::1"}
        )
