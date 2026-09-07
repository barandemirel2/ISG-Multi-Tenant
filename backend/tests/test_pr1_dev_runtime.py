from pathlib import Path

import re

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_COMPOSE = REPO_ROOT / "docker-compose.yml"
PROD_COMPOSE = REPO_ROOT / "docker-compose.prod.yml"
DEV_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile.dev"
PROD_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile"
NGINX_CONFIG = REPO_ROOT / "frontend" / "nginx.conf"
CALENDAR = REPO_ROOT / "frontend" / "src" / "components" / "ui" / "calendar.jsx"
README = REPO_ROOT / "README.md"


def _compose(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_compose_files_have_no_explicit_container_names():
    for path in (DEV_COMPOSE, PROD_COMPOSE):
        services = _compose(path)["services"]
        assert all("container_name" not in service for service in services.values())


def test_development_frontend_uses_source_bind_and_managed_dependencies():
    compose = _compose(DEV_COMPOSE)
    volumes = compose["services"]["frontend"]["volumes"]
    assert "./frontend:/app" in volumes
    assert "frontend_node_modules:/app/node_modules" in volumes
    dependency_volume = compose["volumes"]["frontend_node_modules"]
    assert not dependency_volume or "external" not in dependency_volume
    assert not dependency_volume or "name" not in dependency_volume


def test_frontend_dockerfiles_use_reproducible_npm_ci():
    for path in (DEV_DOCKERFILE, PROD_DOCKERFILE):
        text = path.read_text(encoding="utf-8")
        assert "RUN npm ci" in text
        assert "--force" not in text
        assert "--legacy-peer-deps" not in text
        assert "npm install ajv" not in text


def test_development_frontend_binds_to_container_interface():
    compose = _compose(DEV_COMPOSE)
    assert str(compose["services"]["frontend"]["environment"]["HOST"]) == "0.0.0.0"
    assert "HOST=0.0.0.0" in DEV_DOCKERFILE.read_text(encoding="utf-8")


def test_nginx_keeps_api_backend_proxy():
    nginx = NGINX_CONFIG.read_text(encoding="utf-8")
    assert "location /api/" in nginx
    # The proxy_pass directive may be either the literal compose form
    # (http://backend:8000) or the Railway-runtime-variable form
    # (${BACKEND_UPSTREAM}). Either is acceptable; the reverse-proxy
    # contract is the intent, not the literal URL.
    assert (
        "proxy_pass http://backend:8000;" in nginx
        or "proxy_pass ${BACKEND_UPSTREAM};" in nginx
    ), "Nginx /api/ location must keep the reverse-proxy directive"


def test_readme_uses_actual_swagger_path():
    readme = README.read_text(encoding="utf-8")
    assert "http://localhost:8000/docs" in readme
    assert "/api/docs" not in readme


def test_calendar_supports_every_day_picker_chevron_orientation():
    calendar = CALENDAR.read_text(encoding="utf-8")
    for orientation, icon in {
        "down": "ChevronDown",
        "left": "ChevronLeft",
        "right": "ChevronRight",
        "up": "ChevronUp",
    }.items():
        assert f"{orientation}: {icon}" in calendar


def test_readme_documents_safe_dependency_volume_refresh():
    readme = README.read_text(encoding="utf-8")
    assert "frontend_node_modules" in readme
    assert "docker compose down -v" in readme
    assert "mongo_data" in readme
    assert "lokal geliştirme veritabanı" in readme
    assert "com.docker.compose.volume=frontend_node_modules" in readme
    assert "docker volume prune" not in readme
    assert "docker system prune" not in readme


# ---------------------------------------------------------------------------
# PR3 — Reproducible production frontend image build
#
# Invariants documented in PR3 §4 (Regression Tests). Each invariant below is a
# targeted semantic assertion against the production Dockerfile, the Nginx
# runtime configuration, and the package metadata; none rely on brittle
# full-file snapshots.
# ---------------------------------------------------------------------------
class TestPr3ProductionFrontendBuild:
    """Lock down the PR3 production builder fix.

    The pre-PR3 builder set ``NODE_ENV=production`` in the builder stage and
    ran ``npm ci`` without an explicit ``--include=dev`` override. npm then
    omitted ``@craco/craco`` (a build-time ``devDependency``), so
    ``npm run build`` failed at ``craco: not found``. The fix is to keep
    ``@craco/craco`` in ``devDependencies`` and force npm to install build-time
    devDependencies explicitly via ``npm ci --include=dev``.
    """

    PROD_TEXT = PROD_DOCKERFILE.read_text(encoding="utf-8")
    NGINX_TEXT = NGINX_CONFIG.read_text(encoding="utf-8")
    PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"

    # 1. Production Dockerfile is a multi-stage Node builder + Nginx runtime.
    def test_production_dockerfile_is_multi_stage_node_builder_nginx_runtime(self):
        import re

        # Both stages must be present.
        assert re.search(
            r"^FROM\s+\S+\s+AS\s+builder\b",
            self.PROD_TEXT,
            re.MULTILINE,
        ), "Production Dockerfile must declare an explicit 'AS builder' stage"
        assert re.search(
            r"^FROM\s+nginx:\S+",
            self.PROD_TEXT,
            re.MULTILINE,
        ), "Production Dockerfile final stage must be Nginx-based"

        # Only one builder stage is needed; the file must not duplicate the
        # Node base image or hide another Node runtime after the Nginx stage.
        node_as_builder = re.findall(
            r"^FROM\s+node:\S+\s+AS\s+builder\b",
            self.PROD_TEXT,
            re.MULTILINE,
        )
        assert len(node_as_builder) == 1, (
            "Production Dockerfile must declare exactly one Node 'AS builder' stage"
        )

    # 2. Builder runs deterministic ``npm ci`` (not ``npm install``).
    def test_production_builder_uses_deterministic_npm_ci(self):
        assert "npm ci" in self.PROD_TEXT, (
            "Production builder must use deterministic 'npm ci'"
        )
        assert re.search(r"^RUN\s+npm install\b", self.PROD_TEXT, re.MULTILINE) is None, (
            "Production builder must not fall back to 'npm install'"
        )

    # 3. Builder explicitly installs build-time devDependencies.
    def test_production_builder_explicitly_includes_dev_dependencies(self):
        # The override flag must be present; bare ``npm ci`` plus
        # ``NODE_ENV=production`` in the same builder is the very regression
        # PR3 is fixing.
        assert re.search(
            r"npm\s+ci[^\n]*--include=dev\b",
            self.PROD_TEXT,
        ), (
            "Production builder must explicitly include build-time "
            "devDependencies via 'npm ci --include=dev'"
        )

    # 4. Production Dockerfile does not use forbidden flags.
    def test_production_dockerfile_avoids_force_and_legacy_peer_deps(self):
        forbidden_substrings = (
            "--force",
            "--legacy-peer-deps",
            "npm install @craco/craco",
            "npm install craco",
        )
        for bad in forbidden_substrings:
            assert bad not in self.PROD_TEXT, (
                f"Production Dockerfile must not contain '{bad}'"
            )

    # 5. Production builder runs ``npm run build``.
    def test_production_builder_runs_npm_run_build(self):
        assert re.search(
            r"^RUN\s+npm\s+run\s+build\b",
            self.PROD_TEXT,
            re.MULTILINE,
        ), "Production builder must run 'npm run build'"

    # 6. Final stage copies the CRA/CRACO build output to the Nginx static root.
    def test_final_stage_copies_build_output_to_nginx_static_root(self):
        assert re.search(
            r"COPY\s+--from=builder\s+/app/build\s+/usr/share/nginx/html\b",
            self.PROD_TEXT,
        ), (
            "Final stage must copy /app/build from the builder to "
            "/usr/share/nginx/html"
        )

    # 7. Final stage does not copy node_modules or the full /app directory.
    def test_final_stage_does_not_copy_node_modules_or_full_app(self):
        # /app/node_modules must never be copied into the final image.
        assert "/app/node_modules" not in self.PROD_TEXT, (
            "Final stage must not reference /app/node_modules"
        )
        # The final image must not receive the entire source tree.
        assert re.search(
            r"COPY\s+--from=builder\s+/app\s+/",
            self.PROD_TEXT,
        ) is None, (
            "Final stage must not copy the whole /app directory from the builder"
        )
        # package.json / package-lock.json must not bleed into the runtime image.
        assert "package.json" not in self.PROD_TEXT.split(
            "FROM nginx", 1
        )[1], "Final Nginx stage must not copy package.json"
        assert "package-lock.json" not in self.PROD_TEXT.split(
            "FROM nginx", 1
        )[1], "Final Nginx stage must not copy package-lock.json"

    # 8. @craco/craco remains a devDependency.
    def test_craco_remains_a_dev_dependency(self):
        import json

        package = json.loads(self.PACKAGE_JSON.read_text(encoding="utf-8"))
        dev_deps = package.get("devDependencies", {})
        prod_deps = package.get("dependencies", {})
        assert "@craco/craco" in dev_deps, (
            "@craco/craco must remain in devDependencies"
        )

    # 9. @craco/craco is NOT added to production dependencies.
    def test_craco_not_added_to_production_dependencies(self):
        import json

        package = json.loads(self.PACKAGE_JSON.read_text(encoding="utf-8"))
        prod_deps = package.get("dependencies", {})
        assert "@craco/craco" not in prod_deps, (
            "@craco/craco must not be promoted to production dependencies"
        )

    # 10. Nginx still proxies /api to a backend. The proxy target
    #     was made runtime-configurable via the BACKEND_UPSTREAM env
    #     var (compose default = http://backend:8000) so the frontend
    #     can deploy standalone on Railway without the compose DNS.
    #     The /api/ reverse-proxy contract (proxy_pass directive) is
    #     preserved.
    def test_nginx_keeps_api_backend_proxy_after_pr3(self):
        assert "location /api/" in self.NGINX_TEXT
        # The proxy_pass may be either the compose-safe literal or the
        # runtime variable form (Railway patch). Both keep the reverse-
        # proxy contract intact.
        assert (
            "proxy_pass http://backend:8000;" in self.NGINX_TEXT
            or "proxy_pass ${BACKEND_UPSTREAM};" in self.NGINX_TEXT
        ), "Nginx /api/ location must keep the reverse-proxy directive"

    # 10b. When the proxy_pass is the runtime-variable form, the
    #      BACKEND_UPSTREAM env var defaults to the compose-safe
    #      literal in the Dockerfile so local docker-compose keeps
    #      working without any override.
    def test_backend_upstream_default_is_compose_safe(self):
        # Only meaningful when the runtime-variable form is used.
        if "proxy_pass ${BACKEND_UPSTREAM};" not in self.NGINX_TEXT:
            return
        assert "ENV BACKEND_UPSTREAM=http://backend:8000" in self.PROD_TEXT, (
            "BACKEND_UPSTREAM must default to the compose-safe in-network "
            "service target when the runtime-variable form is used"
        )
        # The Dockerfile must NOT hardcode an absolute Railway / public
        # backend URL in BACKEND_UPSTREAM — only the compose default.
        assert "up.railway.app" not in self.PROD_TEXT, (
            "Dockerfile must not bake a Railway public domain into BACKEND_UPSTREAM"
        )

    # 11. SPA fallback is preserved.
    def test_nginx_spa_fallback_remains_intact(self):
        assert "try_files $uri $uri/ /index.html" in self.NGINX_TEXT


# ---------------------------------------------------------------------------
# PR6 — Production frontend Docker healthcheck reliability
#
# The pre-PR6 production frontend Dockerfile healthcheck was:
#
#     HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
#         CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
#
# On ``nginx:1.27-alpine`` (musl libc), BusyBox ``wget`` resolves ``localhost``
# through ``/etc/hosts`` which maps ``localhost`` to both ``127.0.0.1`` and
# ``::1``. The musl resolver returns ``::1`` first, but Nginx only binds
# IPv4 (``listen 80;`` → ``0.0.0.0:80``), so the connection is refused and
# BusyBox ``wget`` does not fall back to IPv4. The HTTP server is reachable
# via the host, but the in-container healthcheck always fails.
#
# The fix is a one-line change in ``frontend/Dockerfile`` that targets the
# explicit IPv4 loopback address. These tests lock the fix in place and
# guard the surrounding contract.
# ---------------------------------------------------------------------------
class TestPr6FrontendHealthcheck:
    """Lock down the PR6 production frontend healthcheck fix.

    Each invariant is a targeted semantic assertion against the production
    Dockerfile plus the supporting Nginx/Docker surface. The tests do not
    depend on a fragile full-line string match.
    """

    PROD_TEXT = PROD_DOCKERFILE.read_text(encoding="utf-8")

    @staticmethod
    def _healthcheck_block(text):
        """Return the HEALTHCHECK directive block from the production Dockerfile.

        Supports both a single-line ``HEALTHCHECK ... CMD ...`` form and the
        multi-line ``HEALTHCHECK ... \\ CMD ...`` continuation form used in
        the committed file. The parser walks forward line-by-line and
        collects every line that belongs to the directive, stopping at the
        first non-continuation line.
        """
        lines = text.splitlines()
        collected = []
        found = False
        for line in lines:
            if not found:
                if line.startswith("HEALTHCHECK"):
                    found = True
                    collected.append(line)
                continue
            # Continuation: previous collected line ended with a backslash,
            # or the current line is indented (Dockerfile line continuation
            # is conventionally indented under the directive).
            prev_continues = bool(collected) and collected[-1].rstrip().endswith("\\")
            if prev_continues or (line and line[0] in (" ", "\t")):
                collected.append(line)
            else:
                break
        assert found, (
            "Production Dockerfile must contain a HEALTHCHECK directive"
        )
        return "\n".join(collected)

    # 1. Production Dockerfile contains a HEALTHCHECK directive.
    def test_production_dockerfile_has_healthcheck(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert block.startswith("HEALTHCHECK"), (
            "Production frontend Dockerfile must define a HEALTHCHECK"
        )
        assert "CMD" in block, (
            "HEALTHCHECK must include a CMD clause"
        )

    # 2. Healthcheck must not target the bare hostname ``localhost``.
    def test_healthcheck_does_not_target_localhost(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "http://localhost/" not in block, (
            "Healthcheck must not target http://localhost/ "
            "(musl resolver prefers ::1 over 127.0.0.1 while Nginx "
            "binds IPv4 only, causing 'Connection refused')"
        )

    # 3. Healthcheck targets the explicit IPv4 loopback host (127.0.0.1),
    #    not the bare ``localhost`` (which resolves to ``::1`` first on
    #    musl/alpine and breaks the IPv4-only nginx binding). The URL is
    #    now ``http://127.0.0.1:${PORT}/`` so Railway / other PaaS
    #    overlays can supply PORT at runtime; the host is unchanged.
    def test_healthcheck_targets_explicit_ipv4_loopback(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "http://127.0.0.1" in block, (
            "Healthcheck must target http://127.0.0.1 (explicit IPv4 "
            "loopback) — not http://localhost (which resolves to ::1 "
            "first on musl/alpine and breaks the IPv4-only nginx binding)"
        )
        assert "http://localhost" not in block, (
            "Healthcheck must not target http://localhost (IPv6-vs-IPv4 "
            "resolution on musl/alpine)"
        )

    # 4. Healthcheck performs a real HTTP request (wget, not process-only).
    def test_healthcheck_performs_real_http_request(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "wget" in block, (
            "Healthcheck must use wget to perform a real HTTP request"
        )
        # The URL must be a real HTTP URL, not just a path probe.
        assert re.search(r"https?://", block), (
            "Healthcheck must target an explicit http(s):// URL"
        )

    # 5. Healthcheck must not silence failures with ``|| true``.
    def test_healthcheck_does_not_silence_failures(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "|| true" not in block, (
            "Healthcheck must not use '|| true' to silence failures"
        )
        # The directive must still fail loudly when the HTTP request fails.
        assert "|| exit 1" in block, (
            "Healthcheck must propagate failures via '|| exit 1' "
            "so Docker sees a non-zero exit code"
        )

    # 6. Healthcheck is not reduced to process-only / PID probes.
    def test_healthcheck_is_not_process_only(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        for token in ("pgrep", "pidof", "ps -", "ps -p"):
            assert token not in block, (
                f"Healthcheck must not be reduced to a process probe "
                f"({token!r}); it must prove Nginx can serve an HTTP response"
            )

    # 7. Healthcheck must not require curl (the base image ships BusyBox wget).
    def test_healthcheck_does_not_depend_on_curl(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "curl" not in block, (
            "Healthcheck must not depend on curl; the production base "
            "image is nginx:alpine which already ships BusyBox wget"
        )

    # 8. Interval, timeout, retries contract is preserved.
    #    PR6 deliberately keeps the pre-PR6 timing values; the regression
    #    is in the URL, not in the cadence. ``start_period`` is not declared
    #    in the production Dockerfile (matches the committed state).
    def test_healthcheck_timing_contract_preserved(self):
        block = self._healthcheck_block(self.PROD_TEXT)
        assert "--interval=30s" in block, (
            "Healthcheck --interval must remain 30s"
        )
        assert "--timeout=5s" in block, (
            "Healthcheck --timeout must remain 5s"
        )
        assert "--retries=3" in block, (
            "Healthcheck --retries must remain 3"
        )
        # start_period is intentionally not declared in the production
        # Dockerfile; the fix is purely address-targeting.
        assert "--start-period" not in block, (
            "Production HEALTHCHECK must not silently introduce "
            "--start-period; PR6 only changes the URL target"
        )

    # 9. Final runtime image remains Nginx-only (no Node, npm, CRACO, builder).
    def test_final_runtime_remains_nginx_only(self):
        text = self.PROD_TEXT
        # Only the final stage must be Nginx.
        assert re.search(
            r"^FROM\s+nginx:\S+",
            text,
            re.MULTILINE,
        ), "Final stage must be Nginx-based"
        # No Node, npm, or CRACO may leak into the runtime.
        final_stage = text.split("FROM nginx", 1)[1]
        for forbidden in (
            "node:",
            "npm",
            "@craco/craco",
            "craco",
            "/app/node_modules",
            "package.json",
            "package-lock.json",
        ):
            assert forbidden not in final_stage, (
                f"Final Nginx stage must not reference {forbidden!r}"
            )

    # 10. No application source or backend route was added for this fix.
    def test_no_app_or_backend_route_added_for_healthcheck_fix(self):
        frontend_src = REPO_ROOT / "frontend" / "src"
        if frontend_src.exists():
            for path in frontend_src.rglob("*"):
                if path.is_file() and path.suffix in {
                    ".js", ".jsx", ".ts", ".tsx",
                }:
                    text = path.read_text(encoding="utf-8")
                    assert "/api/health" not in text, (
                        f"{path} must not introduce an /api/health route"
                    )
        # Backend must not gain a dedicated healthcheck endpoint for the fix.
        backend_app = REPO_ROOT / "backend" / "server.py"
        if backend_app.exists():
            text = backend_app.read_text(encoding="utf-8")
            assert "/api/health" not in text, (
                "backend/server.py must not introduce /api/health for PR6"
            )
