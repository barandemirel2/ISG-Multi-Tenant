"""Explicit cookie security policy for authentication cookies.

This module centralizes the cookie attribute contract so login, refresh, and
logout can never drift apart. The policy is loaded and validated exactly once
per process (mirroring the PR0 ``initialize_jwt_secret`` pattern) and exposed
read-only thereafter.

The deployment operator must select a policy explicitly via the environment;
no protocol is inferred from request headers, the request URL, ``Host``,
``Origin``, ``X-Forwarded-Proto``, the current hostname, or whether the caller
is localhost. Inference-based security downgrades are precisely the failure
mode PR4 fixes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping, Optional


SAMESITE_LITERAL = Literal["lax", "strict", "none"]
_ALLOWED_SAMESITE: tuple[str, ...] = ("lax", "strict", "none")
_TRUE_LITERAL: str = "true"
_FALSE_LITERAL: str = "false"


@dataclass(frozen=True)
class CookiePolicy:
    """Immutable cookie security policy.

    Attributes
    ----------
    secure:
        Whether authentication cookies carry the ``Secure`` attribute.
    samesite:
        The normalized ``SameSite`` mode. Only ``"lax"``, ``"strict"``, or
        ``"none"`` are accepted. ``"none"`` is only valid when ``secure=True``.
    """

    secure: bool
    samesite: SAMESITE_LITERAL

    def __post_init__(self) -> None:
        if not isinstance(self.secure, bool):
            raise RuntimeError(
                "CookiePolicy.secure must be a bool; got "
                f"{type(self.secure).__name__}"
            )
        if self.samesite not in _ALLOWED_SAMESITE:
            raise RuntimeError(
                f"CookiePolicy.samesite must be one of {_ALLOWED_SAMESITE!r}; "
                f"got {self.samesite!r}"
            )
        if self.samesite == "none" and not self.secure:
            raise RuntimeError(
                "CookiePolicy: SameSite=None requires Secure=true. "
                "Browsers reject SameSite=None cookies without Secure."
            )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _parse_strict_bool(name: str, raw: object) -> bool:
    """Parse a strict boolean environment value.

    Accepts only the canonical boolean strings ``true`` / ``false``.
    Case-insensitive; tolerant of surrounding whitespace. Aliases such as
    ``1``/``0``, ``yes``/``no``, ``on``/``off`` are deliberately rejected —
    PR4 does not broaden the environment contract beyond what the operator
    is required to type explicitly. Any other value raises a sanitized
    ``RuntimeError`` that never echoes the offending input back to the
    operator (so configuration errors stay safe to log).
    """
    if raw is None:
        raise RuntimeError(
            f"{name} is required. Set it to a boolean (true|false) "
            "in the environment or .env file."
        )
    if not isinstance(raw, str):
        raise RuntimeError(
            f"{name} must be a string. Set it to a boolean "
            "(true|false) in the environment or .env file."
        )
    stripped = raw.strip()
    if not stripped:
        raise RuntimeError(
            f"{name} must not be empty. Set it to a boolean "
            "(true|false) in the environment or .env file."
        )
    lowered = stripped.lower()
    if lowered == _TRUE_LITERAL:
        return True
    if lowered == _FALSE_LITERAL:
        return False
    raise RuntimeError(
        f"{name} has an unrecognised boolean value. "
        "Use true|false (case-insensitive)."
    )


def _parse_samesite(name: str, raw: object) -> SAMESITE_LITERAL:
    """Parse and normalize the ``SameSite`` mode.

    Case-insensitive input is normalized to lowercase. Any other value
    raises a sanitized ``RuntimeError``. The error deliberately does NOT
    echo the offending value back to the operator so it is safe to log.
    """
    if raw is None:
        raise RuntimeError(
            f"{name} is required. Choose one of: lax, strict, none."
        )
    if not isinstance(raw, str):
        raise RuntimeError(
            f"{name} must be a string. Choose one of: lax, strict, none."
        )
    normalized = raw.strip().lower()
    if not normalized:
        raise RuntimeError(
            f"{name} must not be empty. Choose one of: lax, strict, none."
        )
    if normalized not in _ALLOWED_SAMESITE:
        raise RuntimeError(
            f"{name} is not a supported SameSite mode. "
            "Choose one of: lax, strict, none."
        )
    return normalized  # type: ignore[return-value]


def validate_cookie_policy(env: Optional[Mapping[str, str]] = None) -> CookiePolicy:
    """Validate a cookie policy from the given mapping.

    ``env`` defaults to ``os.environ`` for production use. Tests pass an
    explicit mapping to keep results deterministic and free of runner
    environment leakage.
    """
    source = os.environ if env is None else env
    secure = _parse_strict_bool("COOKIE_SECURE", source.get("COOKIE_SECURE"))
    samesite = _parse_samesite("COOKIE_SAMESITE", source.get("COOKIE_SAMESITE"))
    return CookiePolicy(secure=secure, samesite=samesite)


# ---------------------------------------------------------------------------
# Process-lifetime cache (mirrors PR0 ``_JWT_SECRET`` pattern)
# ---------------------------------------------------------------------------
_COOKIE_POLICY: Optional[CookiePolicy] = None


def initialize_cookie_policy(env: Optional[Mapping[str, str]] = None) -> CookiePolicy:
    """Validate the cookie policy and cache it for the lifetime of the process.

    Must be called from application startup before any cookie is created.
    Re-initializing with a different value is allowed (used by tests). The
    production startup path calls this exactly once.
    """
    global _COOKIE_POLICY
    _COOKIE_POLICY = validate_cookie_policy(env)
    return _COOKIE_POLICY


def get_cookie_policy() -> CookiePolicy:
    """Return the cached cookie policy.

    Raises ``RuntimeError`` if initialization has not yet happened, instead
    of silently re-reading ``os.environ`` (which would let runtime mutations
    change the cookie security contract after the process is up).
    """
    if _COOKIE_POLICY is None:
        raise RuntimeError(
            "Cookie policy has not been initialized. "
            "Call initialize_cookie_policy() during application startup."
        )
    return _COOKIE_POLICY


def reset_cookie_policy_cache() -> None:
    """Clear the cookie policy cache. Test-only helper.

    Allows tests to drop the cached policy without leaking state across test
    functions.
    """
    global _COOKIE_POLICY
    _COOKIE_POLICY = None