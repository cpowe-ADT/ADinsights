#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

VENV_DIR="backend/.venv-tests"
PY=${PY:-python3}

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at $VENV_DIR";
  $PY -m venv "$VENV_DIR";
fi

"$VENV_DIR/bin/python" -m pip install -q --upgrade pip

# Minimal, pinned deps for tests/lint only (no secrets)
"$VENV_DIR/bin/python" -m pip install -q \
  django~=5.0 \
  djangorestframework~=3.15 \
  djangorestframework-simplejwt~=5.3 \
  celery~=5.3 \
  django-environ~=0.11 \
  croniter~=6.0 \
  cryptography~=43.0 \
  boto3~=1.34 \
  httpx~=0.27 \
  prometheus-client~=0.20 \
  pytest~=8.3 \
  pytest-django~=4.8 \
  ruff~=0.4

echo "Running ruff..."
"$VENV_DIR/bin/ruff" check backend

echo "Running pytest..."
export DJANGO_SECRET_KEY="test-secret-key"
export DATABASE_URL="sqlite:///./test.db"
export DJANGO_DEBUG="true"
export CELERY_BROKER_URL="memory://"
export CELERY_RESULT_BACKEND="cache+memory://"
export REDIS_URL="redis://localhost:6379/0"
export KMS_KEY_ID="test-kms-key"
export KMS_REGION="us-east-1"
"$VENV_DIR/bin/pytest" -q backend
