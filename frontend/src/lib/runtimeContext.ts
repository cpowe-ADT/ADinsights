export type RuntimeContextPayload = {
  client_origin?: string;
  client_port?: number;
  dataset_source?: string;
};

function getClientOrigin(): string | undefined {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return undefined;
  }
  return window.location.origin;
}

function getClientPort(): number | undefined {
  if (typeof window === 'undefined' || !window.location) {
    return undefined;
  }
  const raw = window.location.port;
  if (!raw) {
    return undefined;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function buildRuntimeContextPayload(datasetSource?: string): RuntimeContextPayload {
  const context: RuntimeContextPayload = {
    client_origin: getClientOrigin(),
    client_port: getClientPort(),
  };
  const normalizedDataset = typeof datasetSource === 'string' ? datasetSource.trim() : '';
  if (normalizedDataset) {
    context.dataset_source = normalizedDataset;
  }
  return context;
}
