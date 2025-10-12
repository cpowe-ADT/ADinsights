#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
BI_DIR="$ROOT_DIR/bi/superset"

if ! command -v docker-compose >/dev/null && ! command -v docker >/dev/null; then
  echo "Docker is required" >&2
  exit 1
fi

echo "Building frontend image"
docker build -t ghcr.io/adinsights/frontend:latest "$FRONTEND_DIR"

echo "Building backend image"
docker build -t ghcr.io/adinsights/backend:latest "$BACKEND_DIR"

echo "Building scheduler image"
docker build -f "$BACKEND_DIR/Dockerfile.scheduler" -t ghcr.io/adinsights/scheduler:latest "$BACKEND_DIR"

echo "Packaging Superset artifacts"
tar -czf "$ROOT_DIR/dist-superset.tar.gz" -C "$BI_DIR" .

echo "Deploying stack with docker compose"
(cd "$ROOT_DIR/deploy" && docker compose up -d)

echo "Deployment kicked off. Monitor logs with: docker compose logs -f"
