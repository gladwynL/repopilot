# syntax=docker/dockerfile:1
# RepoPilot web: built SPA served by Caddy, which also reverse-proxies /api to the backend.
# Build context is frontend/.

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Same-origin deployment: the browser calls /api on the page's own origin.
ENV VITE_API_BASE_URL=""
RUN npm run build


FROM caddy:2.11-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
