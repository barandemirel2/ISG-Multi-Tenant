"""Explicit documentation-surface configuration for the FastAPI app.

This module centralizes the contract for the FastAPI auto-generated
documentation routes (``/docs``, ``/redoc``, ``/openapi.json``). The
deployment operator selects whether to expose them via the
``DOCS_ENABLED`` environment variable.

Semantics
---------

==================  =========================================
``DOCS_ENABLED``    Result
==================  =========================================
unset / empty       ``True`` (local development convenience)
``true``            ``True``
``false``           ``False``
other               ``RuntimeError`` at import time
==================  =========================================

The parser is intentionally strict: only the canonical boolean literals
``true`` / ``false`` (case-insensitive, surrounding whitespace tolerated)
are accepted. Aliases such as ``1``/``0``, ``yes``/``no``, ``on``/``off``
are deliberately rejected — mirroring the PR4 ``COOKIE_SECURE``
contract.

The motivating deployment is Railway-hosted UAT, where the
``DOCS_ENABLED=false`` setting closes the public Swagger / ReDoc surface
without touching the application routes that the UAT users actually
call. The default leaves local Docker development untouched.
"""
from __future__ import annotations

import os
from typing import Mapping, Optional


def parse_docs_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Resolve the ``DOCS_ENABLED`` contract.

    ``env`` defaults to ``os.environ`` for production use. Tests pass an
    explicit mapping to keep results deterministic and free of runner
    environment leakage.

    Returns ``True`` when the variable is unset or empty (the default
    preserves local development convenience). Returns ``True`` for
    ``"true"`` (case-insensitive) and ``False`` for ``"false"``
    (case-insensitive). Any other value raises a sanitized
    ``RuntimeError`` that does not echo the offending input back to the
    operator (so configuration errors stay safe to log).
    """
    source = os.environ if env is None else env
    raw = source.get("DOCS_ENABLED")
    if raw is None:
        return True
    if not isinstance(raw, str):
        raise RuntimeError(
            "DOCS_ENABLED must be a string. Set it to true|false "
            "in the environment or .env file."
        )
    stripped = raw.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise RuntimeError(
        "DOCS_ENABLED has an unrecognised boolean value. "
        "Use true|false (case-insensitive)."
    )


def resolve_docs_kwargs(env: Optional[Mapping[str, str]] = None) -> dict:
    """Return the ``docs_url`` / ``redoc_url`` / ``openapi_url`` kwargs
    to pass to ``FastAPI(...)`` for the given environment.

    The returned dict always contains all three keys. When DOCS is
    enabled, the FastAPI defaults (``/docs``, ``/redoc``,
    ``/openapi.json``) are returned. When DOCS is disabled, all three
    values are ``None``, which deactivates the routes.
    """
    if parse_docs_enabled(env):
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
