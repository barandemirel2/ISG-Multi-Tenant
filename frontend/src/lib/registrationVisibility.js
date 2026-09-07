// P0 — Public registration UX gate.
//
// The authoritative security boundary lives in the backend
// (``ENABLE_PUBLIC_REGISTRATION`` in ``backend/registration_config.py``).
// This module is the **frontend mirror**: it only controls whether the
// registration link/button is rendered in the UI and whether the
// ``/register`` route is reachable. It MUST NOT be treated as a
// security boundary. If the frontend flag is ``true`` but the backend
// flag is ``false`` (or vice versa), the backend wins — the route
// handler returns 404 and no account is created.
//
// Reading the flag
// ----------------
//
// ``REACT_APP_PUBLIC_REGISTRATION_ENABLED`` is a build-time CRA env
// variable. We accept only the canonical boolean literals ``true`` /
// ``false`` (case-insensitive, optional surrounding whitespace). The
// shape mirrors the backend parser so operators see consistent
// behavior end-to-end. Aliases (``1`` / ``0`` / ``yes`` / ``on``) are
// deliberately rejected — same convention as ``COOKIE_SECURE`` /
// ``DOCS_ENABLED`` / ``ENABLE_PUBLIC_REGISTRATION``. The rejected
// branch returns ``false`` (closed), so a typo does not accidentally
// expose the registration flow in production.
//
// ``env`` defaults to ``process.env`` for production. Tests pass an
// explicit mapping so results are free of runner leakage. The function
// is pure and side-effect-free.

const TRUE_LITERAL = "true";
const FALSE_LITERAL = "false";

function parseBoolLiteral(raw) {
  if (raw == null) return null;
  if (typeof raw !== "string") {
    throw new Error(
      "REACT_APP_PUBLIC_REGISTRATION_ENABLED must be a string. " +
        "Set it to true|false at build time."
    );
  }
  const stripped = raw.trim();
  if (!stripped) return null;
  const lowered = stripped.toLowerCase();
  if (lowered === TRUE_LITERAL) return true;
  if (lowered === FALSE_LITERAL) return false;
  throw new Error(
    "REACT_APP_PUBLIC_REGISTRATION_ENABLED has an unrecognised boolean value. " +
      "Use true|false (case-insensitive)."
  );
}

/**
 * Resolve the frontend public-registration flag from a given env
 * mapping. Defaults to ``false`` (closed) when unset / empty / blank.
 *
 * @param {Object} [env] - Environment mapping; defaults to
 *   ``process.env``. Tests pass an explicit object for determinism.
 * @returns {boolean} ``true`` only when the operator has explicitly
 *   enabled the flag with a canonical literal.
 */
export function parsePublicRegistrationEnabled(env) {
  const source = env || (typeof process !== "undefined" ? process.env : {});
  return parseBoolLiteral(source.REACT_APP_PUBLIC_REGISTRATION_ENABLED) === true;
}

/**
 * Module-level snapshot. Computed once at import time from
 * ``process.env``. Same lifetime as the module: the build embeds the
 * resolved value, runtime mutations of ``process.env`` are not observed
 * by callers that already imported this module. This is intentional —
 * CRA env vars are baked at build time, not runtime-mutable.
 *
 * Tests that need to exercise the opposite branch should
 * ``jest.resetModules()`` and re-import this module after patching
 * ``process.env``. See ``registrationVisibility.test.js`` for the
 * canonical pattern.
 */
export const PUBLIC_REGISTRATION_ENABLED = parsePublicRegistrationEnabled();

/**
 * Read the resolved public-registration flag as a function call.
 *
 * Production callers should prefer this function over reading the
 * module-level constant directly because:
 *
 * 1. It exposes the read through a stable module symbol, so test
 *    fixtures can ``jest.mock`` it (e.g. with a factory returning
 *    ``() => true``) without resetting React or other consumers.
 * 2. The returned value is the same constant, so the runtime cost is
 *    negligible — a single property access.
 *
 * The function deliberately reads the module-level constant (not
 * ``process.env``) so it stays consistent with the build-time
 * "baked at import" semantic of ``PUBLIC_REGISTRATION_ENABLED``.
 */
export function isPublicRegistrationEnabled() {
  return PUBLIC_REGISTRATION_ENABLED;
}
