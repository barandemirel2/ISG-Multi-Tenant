# syntax=docker/dockerfile:1.7
FROM node:20-bookworm-slim AS builder

ARG REACT_APP_BACKEND_URL=/api
ENV CI=true \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NODE_ENV=production \
    REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --include=dev

COPY . .

RUN npm run build

FROM nginx:1.27-alpine

# Default frontend listen port. Railway / other PaaS overlays supply PORT
# at runtime; the nginx template substitution below expands ${PORT} when
# the container starts. Keeping the default at 80 preserves local
# docker-compose behaviour (the image still listens on 80 with no PORT
# override).
ENV PORT=80

# Backend upstream for the /api/ reverse-proxy. Local docker-compose keeps
# the safe default of the in-network service name ``backend:8000`` so the
# reverse proxy actually forwards traffic inside compose development.
#
# On Railway the documented split-host mode sets BACKEND_UPSTREAM to a
# startup-safe placeholder (e.g. ``http://127.0.0.1:9999``); the React
# bundle makes API calls to the absolute backend origin baked at build
# time via ``REACT_APP_BACKEND_URL``, so the /api/ proxy itself is dormant
# and never serves Railway browser traffic. The placeholder exists ONLY
# so nginx can resolve an upstream name at container start — see
# docs/RAILWAY_UAT.md.
ENV BACKEND_UPSTREAM=http://backend:8000

# Drop the stock default server config — our template takes its place.
RUN rm /etc/nginx/conf.d/default.conf

# The official nginx image's entrypoint runs envsubst on every file in
# /etc/nginx/templates/*.template and writes the result to /etc/nginx/conf.d.
# This is the supported way to wire the runtime PORT into the listen
# directive without rewriting the image's bootstrap.
COPY nginx.conf /etc/nginx/templates/default.conf.template

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

# Healthcheck must probe the SAME effective port the server is bound to.
# Shell-form so the runtime ${PORT} is expanded at container start.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD sh -c "wget --quiet --tries=1 --spider http://127.0.0.1:${PORT}/ || exit 1"

CMD ["nginx", "-g", "daemon off;"]
