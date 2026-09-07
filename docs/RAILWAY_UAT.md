# Railway UAT deployment guide

This guide documents the **source-side contract** the Railway UAT
deployment relies on. It does **not** provision Railway resources, does
not log in to Railway, and does not deploy. The Railway-side wiring
(values, volumes, Atlas cluster) is the human operator's responsibility.

The repository adaptation is intentionally minimal: a small
``DOCS_ENABLED`` switch, a ``PORT``-honoring CMD in both Dockerfiles, and
the nginx template substitution. Application code, domain logic, the
84-question seed, audit state machine, audit log, S6 export contract,
DÖF rules, photo upload storage path, and cookie semantics are all
untouched.

---

## Architecture

```
Railway
├── frontend  (public; nginx serving the React build)
├── backend   (public; FastAPI + uvicorn)
│   └── Volume mounted at /app/uploads  (photo evidence persistence)
└── (no Mongo service on Railway — external Atlas below)

External
└── MongoDB Atlas cluster (mongodb+srv://…)
```

The backend service is the only piece that reaches Atlas. The frontend
service talks to the backend through the URL Railway gave the backend
service and configured via ``REACT_APP_BACKEND_URL`` at build time.

---

## Backend service

| Setting        | Value |
|----------------|-------|
| Service root   | `backend/` |
| Build          | `backend/Dockerfile` |
| Public         | yes (Railway must reach the healthcheck) |
| Healthcheck    | `GET /api/` (Docker HEALTHCHECK probes the same effective PORT) |
| Default port   | `8000` (overridden by Railway's `PORT` at runtime) |
| Required runtime vars | `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `CORS_ORIGINS`, `DOCS_ENABLED`, `VERIFICATION_BASE_URL` |
| Mounted volume | `/app/uploads` (Railway Volume) |

The startup path on first deploy runs:

1. `users.email` unique index
2. `audits.user_id` index
3. `audit_ibraz` indexes (verification collection)
4. `templates.code` unique index
5. `isg_v1_default` template (84-question seed) — idempotent
6. Admin user seeded from `ADMIN_EMAIL` / `ADMIN_PASSWORD`
7. `templates` cache loaded

Demo audits are **not** auto-seeded from startup. The demo create
audit command stays an explicit developer action.

---

## Frontend service

| Setting        | Value |
|----------------|-------|
| Service root   | `frontend/` |
| Build          | `frontend/Dockerfile` |
| Public         | yes |
| Healthcheck    | `GET /` (HEAD via `wget --spider`) |
| Default port   | `80` (overridden by Railway's `PORT` at runtime) |
| Required **build** var | `REACT_APP_BACKEND_URL` |
| Required **runtime** var | `BACKEND_UPSTREAM` (startup-safety placeholder; see below) |

The frontend is a static SPA behind nginx. The nginx config is mounted
as `nginx.conf` and copied into `/etc/nginx/templates/` so the official
nginx image's entrypoint substitutes the listed variables at container
start: ``${PORT}`` (listen directive + HEALTHCHECK) and
``${BACKEND_UPSTREAM}`` (the ``/api/`` reverse-proxy target).

### Railway networking mode (this UAT's documented and locally verified mode — split-host browser-direct)

This UAT deployment uses **split-host browser-direct API traffic**.
The browser hits the backend directly; the in-tree nginx ``/api/``
reverse proxy is **dormant**.

* **Build-time arg**: `REACT_APP_BACKEND_URL=https://<backend-public-origin>`
  — the absolute HTTPS origin Railway assigns to the backend service.
  The React bundle calls the backend directly. **A frontend rebuild is
  required** when this value changes (CRA build-time injection).
* **Runtime var**:    `BACKEND_UPSTREAM=http://127.0.0.1:9999`
  — a startup-safe placeholder so nginx can resolve an upstream name
  at container start. **The /api/ proxy never serves Railway browser
  traffic** in this mode.
* Cookies are **cross-site** (`COOKIE_SAMESITE=none` +
  `COOKIE_SECURE=true`) because the frontend and backend live at
  different origins.

The local Docker Compose default keeps the in-tree ``/api/`` proxy
working by leaving ``BACKEND_UPSTREAM`` at its image default
(``http://backend:8000``, the in-network service name). No change is
required for local development.

### `BACKEND_UPSTREAM` — startup-safety placeholder

Defined in `frontend/Dockerfile` as:

```dockerfile
ENV BACKEND_UPSTREAM=http://backend:8000
```

Substituted into ``proxy_pass`` at container start by the official
nginx image's ``envsubst`` pass (the same mechanism that expands
``${PORT}``). The image default is the in-network docker-compose
service name. On Railway — where the frontend is a standalone service
with no Compose ``backend`` neighbour — the operator **must** set
``BACKEND_UPSTREAM`` to a startup-safe placeholder, otherwise nginx
aborts with ``host not found in upstream "backend"``.

> **No Railway hostname is hardcoded in source.** The Dockerfile
> default is only the compose-safe literal. Any absolute Railway
> hostname is supplied by the operator at deploy time.

> **Changing `REACT_APP_BACKEND_URL` requires a frontend rebuild.**
> It is a CRA build-time variable, not a runtime variable.

### Same-origin reverse-proxying — NOT PART OF THIS UAT DEPLOYMENT / NOT VALIDATED HERE

A single-origin layout where the browser hits the frontend and nginx
proxies ``/api/`` to a Railway backend hostname
(``BACKEND_UPSTREAM=http://<backend-service>.up.railway.app`` together
with ``REACT_APP_BACKEND_URL=/api``) is a possible **future
architecture**. It is **NOT** part of this UAT deployment and has
**NOT** been validated in this patch. That mode would require
additional work to validate:

* Railway-internal DNS resolution from the frontend container to the
  backend hostname (private-network reachability).
* HTTPS host-header routing through nginx ``proxy_pass`` with the
  correct ``Host:`` rewriting for an arbitrary upstream hostname.
* ``resolver`` / upstream-by-variable wiring if the Railway hostname
  resolves to ephemeral IPs.

None of these were exercised in the isolated-startup proof for this
patch. Use the documented split-host mode above unless that additional
work is done explicitly.

---

## MongoDB

External MongoDB Atlas. No Mongo service is provisioned on Railway.

* `MONGO_URL=mongodb+srv://…` (driver accepts this natively)
* `DB_NAME=risk_analiz_uat` (recommended for the UAT environment; do
  not reuse the production DB name)
* Seed bootstrap (indexes, 84-question template, admin) is unchanged
  and runs on first successful backend start.

---

## Volume

The backend service mounts a Railway Volume at `/app/uploads`. The
backend writes photo evidence to `/app/uploads/photos/<yyyy>/<mm>/…`
and serves it via `GET /uploads/…`. The URL contract is unaffected by
the storage backing: the same `/uploads/...` path works whether the
storage is a bind mount, a named volume, or a Railway Volume.

**Do not** migrate photo storage to S3 or any other backend as part of
this UAT. The Railway Volume is the single change.

---

## Cookie / CORS contract

The Railway frontend is served over HTTPS under a different origin than
the backend, so the cross-site cookie profile applies:

| Variable          | Value |
|-------------------|-------|
| `COOKIE_SECURE`   | `true` |
| `COOKIE_SAMESITE` | `none` |
| `CORS_ORIGINS`    | the **exact** frontend origin (no trailing slash) |

`COOKIE_SAMESITE=none` requires `COOKIE_SECURE=true`; the backend
refuses to start if the pair is inconsistent. `CORS_ORIGINS` must be
the exact origin the browser sends (scheme + host + port, no path).

Tokens remain HttpOnly in every profile. No value is ever exposed via
client-readable storage.

---

## Docs surface

| Variable        | Value |
|-----------------|-------|
| `DOCS_ENABLED`  | `false` |

`DOCS_ENABLED=false` closes `/docs`, `/redoc`, and `/openapi.json` on
the public backend. Default local development behaviour is unchanged
(`DOCS_ENABLED` unset ⇒ docs enabled).

The parser only accepts the canonical literals `true` / `false`
(case-insensitive). Any other value fails the backend at startup.

---

## First-deploy order

This is the minimum ordering that avoids cookie / CORS / build-arg
chicken-and-egg. Secrets are referenced by **name only**; provide
real values through the Railway UI.

1. Provision the backend service in Railway (no public domain yet).
2. Set `MONGO_URL` + `DB_NAME` on the backend service.
3. Deploy the backend. Confirm the healthcheck goes green.
4. Provision the frontend service. Set `REACT_APP_BACKEND_URL` to the
   backend's HTTPS origin (the documented split-host mode — do NOT set
   it to `/api` for Railway; that proxy-mode layout is not part of
   this UAT and has not been validated). Set
   `BACKEND_UPSTREAM=http://127.0.0.1:9999` as the startup-safe
   placeholder for the dormant nginx `/api/` proxy.
5. Issue a public frontend domain on Railway.
6. Set `CORS_ORIGINS` on the backend to the **exact** frontend origin
   (no trailing slash).
7. Trigger a frontend rebuild + deploy so the SPA actually uses the
   chosen `REACT_APP_BACKEND_URL`.
8. Smoke-test: log in as the seeded admin.
9. Smoke-test: upload a photo into a new audit.
10. Restart the backend so the new upload path is on the persistent
    volume.
11. Verify the photo persists after a fresh container restart.
12. Export the audit as PDF.
13. Export the audit as Excel.
14. Open the verification QR / link and confirm the public verify
    endpoint resolves against `VERIFICATION_BASE_URL`.

---

## What this guide does **not** do

* It does not create Atlas, Railway projects, or Railway services.
* It does not log in to Railway.
* It does not push or deploy any branch.
* It does not store real secrets.

The repository is left UNCOMMITTED for human review; this guide is the
operational reference for whoever performs the first deploy.
