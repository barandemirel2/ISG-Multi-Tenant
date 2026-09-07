# ARRODES.md — Architecture & Domain Map (ABCD Tech Solutions İSG Risk Analiz)

Fast orientation map for coding agents. Operational rules: see `AGENTS.md`.

## Project purpose

ABCD Tech Solutions İSG (İş Sağlığı ve Güvenliği) Risk Analiz application: restaurant audits
with a risk questionnaire, DÖF (Düzeltici Önleyici Faaliyet) lifecycle, final
export, retention and ibraz (presentation/verification) of audit evidence.

---

## Backend map (`backend/`)

| File | Responsibility |
|---|---|
| `server.py` | FastAPI app: auth (JWT httpOnly cookies), audits CRUD, answers, DÖF lifecycle, soft-delete, exports (Excel/PDF), ibraz records, verify endpoint, admin endpoints, retention/archive, audit logging. ~4.5k lines; keep changes surgical. |
| `audit_state.py` | `AuditState` enum + `TRANSITIONS` + transition guards (`can_edit_*`, `can_export_*`). Single source of truth for the state machine. |
| `audit_log.py` | Append-only `audit_log` collection writes (`log_action`), retention computation (`compute_retention_until`), archive (`archive_expired`). |
| `audit_columns.py` | **S6**: the single shared 11-column definition consumed by BOTH Excel and PDF export. Changing columns here changes both exports. |
| `tests/` | Deterministic pytest suite (mongomock + httpx, no live DB needed). |

## Frontend map (`frontend/src/`)

Key pages (`pages/`): `AuditFormPage` (audit + answers + inline DÖF), `DashboardPage`
(KPIs, audit list), `DofPage` (DÖF review/close), `UatChecklistPage` (internal UAT
checklist), `NewAuditPage`, `LoginPage`, `RegisterPage`.

Key components (`components/`): `InlineDofForm` (inline DÖF creation on HAYIR answers),
`AuditStateBadge` (state display), `ConfirmDestructive` (destructive-action guard),
`DofApproveModal`, `DofTimeline`, `AuditHistoryPanel`, `PhotoUploader`, `BrandLogos`
(local logo handling for exports), plus export/verification UI on the audit page.

## Audit state machine

```text
DRAFT
 ├─ no active HAYIR → DOF_CLOSED
 └─ active HAYIR    → DOF_OPEN

DOF_OPEN
 └─ all active DÖF resolved → DOF_CLOSED

DOF_CLOSED
 └─ valid final export → FINAL

FINAL
 └─ terminal / immutable
```

Legacy `SUBMITTED` remains for backward compatibility where applicable
(`derive_is_completed` maps it as completed).

## DÖF lifecycle

* **Active DÖF**: a HAYIR answer whose DÖF is open — keeps audit in `DOF_OPEN`.
* **Closed DÖF**: resolved (EVET/NA transition or explicit closure) — contributes to `DOF_CLOSED`.
* **Invalidated historical DÖF**: retained for evidence, never active again.
* **HAYIR → EVET/NA**: activates/refreshes or closes DÖF records per transition rules.
* Historical DÖF evidence is **never physically deleted**.

## Soft-delete

Normal application flows filter to active/non-deleted audits (`deleted_at == None`).
Admin/forensic/retention paths may intentionally access retained records
(e.g. `?include_archived=true`). Soft-deleted records are excluded from normal scope.

## Audit log

* Append-only intent: every domain mutation writes an `audit_log` entry (who, when, what, before/after, IP).
* Mandatory compliance logging: critical mutations (submit, answer updates, DÖF changes, ibraz export, photo upload) use `mandatory=True` — log failure surfaces as a visible error (5xx).
* **Known limitation**: mutation write and log write are separate operations, not a single transaction. Some paths (export logging) are best-effort on failure. Do not claim transactional atomicity.

## Brand selection — workspace / UI filter, NOT a security boundary

The selected brand (``tab_selected_brand`` in the client + the
`selectedBrand` field on audit reads) is **a per-browser workspace
preference**, used to slice the dataset the active user is looking at
and to label the UI chrome. It is not a tenant boundary and does not
substitute for backend authorization.

* **Real security boundary (unchanged):** the canonical model is
  authenticated user → ``_scope_filter(current_user)`` → server-side
  authorization, applied to every audit-reading endpoint
  (``/api/audits``, ``/api/dofs``, ``/api/exports/*``, ``/api/audit/*``,
  etc.). Adding brand selection does **not** replace or weaken these
  gates.
* **What brand selection does:** frontend UI filter (e.g. DÖF list
  brand chip via `filterDofs({ brand })`); frontend brand chrome
  (logo / "Marka Seç" button) and as a soft hint that ``RootRedirect``
  uses to redirect a missing-brand user to ``/brand-selection``.
* **What brand selection does NOT do:** it does **not** elevate
  authority (an admin without brand X still only sees brand X items
  they're scoped to); it does **not** create a per-brand role; it does
  **not** hide audits the user is authorized to see at the server
  level. A malicious client can always craft requests without
  ``selectedBrand`` and still receive everything they're authorized
  for — the server's ``_scope_filter`` is the only thing that can say
  no.
* **Endpoint development rule:** any new endpoint that returns
  audit/DÖF/photo/ibraz data MUST keep the existing
  ``_scope_filter(current_user)`` (or equivalent role/permission check).
  A new feature never weakens the existing boundary just because a
  brand was selected in the UI.
* **Lifecycle:** ``selectedBrand`` is a per-browser preference. On
  logout, ``BrandAuthSync`` clears it so the next user of the same
  browser does not inherit the previous user's workspace. See
  `frontend/src/components/BrandAuthSync.jsx`.

## İbraz

* Canonical evidence hash: `_compute_ibraz_hash` → canonical JSON (sorted keys) → **SHA-256**.
* `_persist_ibraz_record` writes to `audit_ibraz` collection BEFORE the PDF is generated (QR embeds the ID); idempotent per `(audit_id, ibraz_hash)`.
* Opaque `verification_id` is referenced by the QR; public read-only endpoint `GET /api/verify/{verification_id}` resolves the record and returns tamper-evidence info.
* **SHA-256 ibraz verification is NOT an electronic/qualified signature.**

## Public registration gate (P0)

Production/default posture is **closed**. `POST /api/auth/register`
returns `404 Not Found` unless the deployment operator has explicitly
opted in via the `ENABLE_PUBLIC_REGISTRATION=true` environment variable.
A future admin-managed user flow will own account creation; this gate
is the temporary mitigation.

* `ENABLE_PUBLIC_REGISTRATION` (backend) is the **authoritative
  security boundary**. It is read once at module-import time by
  `backend/registration_config.py` (`is_public_registration_enabled()`).
  Strict parser: only `true` / `false` (case-insensitive, optional
  surrounding whitespace) are accepted; aliases such as `1` / `0` /
  `yes` / `no` are deliberately rejected. Unset / empty value resolves
  to `False` (closed).
* `REACT_APP_PUBLIC_REGISTRATION_ENABLED` (frontend) is **UX-only**.
  When closed, the "Hesap Oluştur" / "Kayıt olun" link is not rendered
  on the login page and direct navigation to `/register` redirects to
  `/login`. Frontend mirror parser has the same strict contract.
* **Backend wins on mismatch.** If the frontend flag is `true` but the
  backend flag is `false`, the registration form may render, but
  `POST /api/auth/register` still returns 404 with no DB write, no
  password hash, no JWT issuance, no auth cookie. The reverse mismatch
  is silent at the wire level (operator chose to keep the surface
  hidden).
* Hiding the route / link in the frontend is **not** a security
  boundary. Treat `REACT_APP_PUBLIC_REGISTRATION_ENABLED` as a UX
  concern and `ENABLE_PUBLIC_REGISTRATION` as the only authoritative
  control.
* Existing login flow (`/api/auth/login`, `/api/auth/logout`,
  `/api/auth/me`, `/api/auth/refresh`, JWT, cookies, `BrandAuthSync`,
  brand selection, existing accounts) is **unaffected** by this gate.
  Admin and reviewer accounts continue to log in normally.

## S6 export contract

Both Excel and PDF consume the shared semantic column definitions from
`backend/audit_columns.py` — exactly 11 columns, in order:

```text
No | Kategori | Tehlike & Risk Maddesi | Cevap | Olasılık (O) | Şiddet (Ş) |
Risk Skoru (R) | Risk Seviyesi | Sorumlu | Termin Süresi | Alınması Gereken Tedbir (DÖF)
```

Changing the column set in `audit_columns.py` changes both exports; the S6 test
(`backend/tests/test_pdf_export_design.py`) pins this contract.

## Retention

`compute_retention_until` = audit `created_at` + **6 calendar years** via
`dateutil.relativedelta` (leap-year-correct calendar arithmetic; plain
`timedelta(days=365*6)` was replaced — B8). `retention_until` set at creation;
`is_archived` soft-marks expired audits. Do not claim a legal trigger beyond the
implemented lifecycle.

## Backup

`POST /api/admin/backup` is an **intentional honest no-op / deprecated** endpoint:
it returns `{ok: true, action: "noop", deprecated: true}` and points operators to
`scripts/backup_mongo.sh` (shell cron; mongodump + s3cmd/s5cmd on host/sidecar).
Ops backup mechanism lives in scripts/docs, not in the app runtime.

## Tests

Canonical commands:

```bash
# Backend deterministic suite (mongomock + httpx, no live DB)
cd backend && pytest

# External backend integration / E2E-style scripts (need a running backend + env credentials)
# e.g. scripts/e2e_dof_summary_test.py (env-driven; no hardcoded credentials)
python scripts/e2e_dof_summary_test.py

# Frontend unit tests
cd frontend && npm test

# Frontend production build
cd frontend && npm run build

# Docker
docker compose up -d --build          # dev (backend :8000, frontend :3000)
docker compose -f docker-compose.prod.yml up -d --build   # single-port production

# E2E prerequisites
#   - backend running with current code (rebuild when HEAD changed)
#   - Mongo up; admin credentials via env, never hardcoded
```

No real credentials anywhere in this document — see `AGENTS.md` → Secret handling.
