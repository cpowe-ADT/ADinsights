FROM node:20-bookworm-slim AS exporter
WORKDIR /opt/adinsights/exporter

COPY integrations/exporter/package*.json ./
RUN npm ci --omit=dev
COPY integrations/exporter/bin ./bin
COPY integrations/exporter/lib ./lib
COPY integrations/exporter/templates ./templates

FROM python:3.11-slim-bookworm AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV REPORT_EXPORTER_DIR=/opt/adinsights/exporter
ENV REPORT_EXPORT_ARTIFACT_ROOT=/var/lib/adinsights/report-exports
ENV CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

RUN apt-get update && \
    apt-get install --no-install-recommends -y chromium && \
    rm -rf /var/lib/apt/lists/*

COPY --from=exporter /usr/local/bin/node /usr/local/bin/node
COPY --from=exporter /opt/adinsights/exporter /opt/adinsights/exporter

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
