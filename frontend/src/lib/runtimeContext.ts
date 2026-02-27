export type RuntimeContextPayload = {
  client_origin?: string;
  client_port?: number;
};

function getClientOrigin(): string | undefined {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return undefined;
  }
  return window.location.origin;
}

function getClientPort(): number | undefined {
  if (typeof window === 'undefined' || !window.location?.port) {
    return undefined;
  }
  const parsed = Number.parseInt(window.location.port, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function buildRuntimeContextPayload(): RuntimeContextPayload {
  return {
    client_origin: getClientOrigin(),
    client_port: getClientPort(),
  };
}

