"""Public registration gate — ``ENABLE_PUBLIC_REGISTRATION`` contract.

P0 hardening. Production/default posture MUST be ``False``: public
``POST /api/auth/register`` MUST NOT create new accounts unless the
deployment operator explicitly opts in. The contract mirrors the
existing strict boolean-parser style used by ``cookie_policy.py`` and
``docs_config.py`` (canonical ``true`` / ``false`` literals only; aliases
such as ``1`` / ``0`` / ``yes`` / ``no`` are deliberately rejected).

This module owns three responsibilities and nothing else:

1. **Pure parser** — :func:`parse_public_registration_enabled` resolves
   the ``ENABLE_PUBLIC_REGISTRATION`` environment variable to a Python
   ``bool``. ``env`` defaults to ``os.environ`` for production; tests
   pass an explicit mapping so results are free of runner leakage.

2. **Centralized helper** — :func:`is_public_registration_enabled` is the
   single authoritative read path used by the ``/api/auth/register``
   route handler in ``server.py``. The gate is *not* a feature flag in
   the user-facing sense — the frontend mirror flag
   ``REACT_APP_PUBLIC_REGISTRATION_ENABLED`` only controls UX visibility
   (login link / route reachability). The backend is the only security
   boundary.

3. **Module-level snapshot** — :data:`_PUBLIC_REGISTRATION_ENABLED`
   captures the resolved value at import time so the route handler can
   answer in O(1) without re-reading ``os.environ`` on every request. We
   intentionally avoid the cached-with-initialize pattern used by
   ``cookie_policy.py`` / ``initialize_jwt_secret`` here because:

   * The value is read by exactly one route handler in this module.
   * The P0 contract is "default off, opt-in only"; we want the wire
     behavior to track ``os.environ`` exactly without an extra init
     surface that could drift.

Semantics
---------

===================  =========================================
``ENABLE_PUBLIC_REGISTRATION``  Result
===================  =========================================
unset / empty       ``False`` (production / default safe)
``true``            ``True``
``false``           ``False``
other               ``RuntimeError`` at import time
===================  =========================================

When ``True`` is resolved, :func:`parse_public_registration_enabled`
performs no further checks; :func:`is_public_registration_enabled`
returns the resolved value verbatim. When ``False`` is resolved, the
route handler short-circuits with ``HTTPException(status_code=404)``
before any DB write, password hash, JWT issuance, or cookie set.

Invalid values raise a sanitized ``RuntimeError`` that does NOT echo
the offending input back to the operator, so configuration errors stay
safe to log. This mirrors the strict-parser convention already used by
``cookie_policy._parse_strict_bool`` and ``docs_config.parse_docs_enabled``.
"""
from __future__ import annotations

import os
from typing import Mapping, Optional


def parse_public_registration_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Resolve the ``ENABLE_PUBLIC_REGISTRATION`` environment variable.

    ``env`` defaults to ``os.environ`` for production use. Tests pass an
    explicit mapping to keep results deterministic and free of runner
    environment leakage.

    Returns ``False`` when the variable is unset or empty (the
    production-safe default — public registration is opt-in only).
    Returns ``True`` for ``"true"`` (case-insensitive) and ``False`` for
    ``"false"`` (case-insensitive). Any other value raises a sanitized
    ``RuntimeError`` that does not echo the offending input back to the
    operator (so configuration errors stay safe to log).

    The strict-parser shape mirrors ``docs_config.parse_docs_enabled``
    (canonical literals only) but with a *flipped* default: this contract
    must default to closed. ``docs_config`` defaults to open because
    /docs is local-dev convenience; registration is a security boundary,
    not a convenience.
    """
    source = os.environ if env is None else env
    raw = source.get("ENABLE_PUBLIC_REGISTRATION")
    if raw is None:
        return False
    if not isinstance(raw, str):
        raise RuntimeError(
            "ENABLE_PUBLIC_REGISTRATION must be a string. Set it to true|false "
            "in the environment or .env file."
        )
    stripped = raw.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise RuntimeError(
        "ENABLE_PUBLIC_REGISTRATION has an unrecognised boolean value. "
        "Use true|false (case-insensitive)."
    )


# Module-level snapshot. Read once at import time. The route handler in
# ``server.py`` resolves the gate via :func:`is_public_registration_enabled`
# which is a thin wrapper over this variable.
_PUBLIC_REGISTRATION_ENABLED: bool = parse_public_registration_enabled()


def is_public_registration_enabled() -> bool:
    """Return the cached resolved value of ``ENABLE_PUBLIC_REGISTRATION``.

    This is the **single authoritative read path** for the public
    registration gate. The ``/api/auth/register`` route handler MUST
    call this helper rather than re-read ``os.environ`` so that:

    * The behavior is consistent across the whole process.
    * The frontend visibility flag ``REACT_APP_PUBLIC_REGISTRATION_ENABLED``
      cannot accidentally widen the backend's contract.
    * Tests can override the resolved value through
      :func:`set_public_registration_enabled_for_tests` without leaking
      env mutations into other tests.

    Returns ``False`` (closed) when the variable is unset or empty —
    the production-safe default.
    """
    return _PUBLIC_REGISTRATION_ENABLED


def set_public_registration_enabled_for_tests(value: bool) -> None:
    """Test-only helper to override the cached gate value.

    Production code MUST NOT call this. The intended use is test fixtures
    that need to exercise both the disabled and enabled branches of the
    route handler without touching the process environment. The fixture
    is responsible for restoring the original value (or letting the
    worker process exit).
    """
    global _PUBLIC_REGISTRATION_ENABLED
    _PUBLIC_REGISTRATION_ENABLED = value


def reset_public_registration_cache() -> None:
    """Test-only helper that re-resolves the gate from ``os.environ``.

    Lets a test fixture drop the cached value and re-evaluate against a
    freshly patched environment. Mirrors the
    ``reset_cookie_policy_cache`` / ``initialize_cookie_policy`` pattern.
    """
    global _PUBLIC_REGISTRATION_ENABLED
    _PUBLIC_REGISTRATION_ENABLED = parse_public_registration_enabled()
