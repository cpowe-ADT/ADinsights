import Ajv, { type DefinedError } from "ajv";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { inspect } from "node:util";

const ajv = new Ajv({ allErrors: true, strict: false });
const validatorCache = new Map<string, Ajv.ValidateFunction>();
const schemaCache = new Map<string, unknown>();

const SCHEMA_DIRECTORY = path.resolve(__dirname, "..", "schemas");

export class SchemaValidationError extends Error {
  constructor(
    readonly schemaName: string,
    readonly errors: ReadonlyArray<DefinedError>,
    readonly payload: unknown,
  ) {
    super(formatErrorMessage(schemaName, errors, payload));
    this.name = "SchemaValidationError";
  }
}

function normalizeSchemaName(name: string): string {
  const trimmed = name.trim();
  const withoutSlashes = trimmed.replace(/^\/+|\/+$/g, "");
  if (!withoutSlashes) {
    throw new Error(`Schema name \"${name}\" resolves to an empty filename.`);
  }
  return withoutSlashes
    .replace(/[\\/]+/g, "-")
    .replace(/[^A-Za-z0-9_.-]+/g, "-")
    .toLowerCase();
}

async function loadSchema(schemaName: string): Promise<unknown> {
  const cached = schemaCache.get(schemaName);
  if (cached) {
    return cached;
  }
  const normalized = normalizeSchemaName(schemaName);
  const schemaPath = path.join(SCHEMA_DIRECTORY, `${normalized}.json`);
  try {
    const raw = await readFile(schemaPath, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    schemaCache.set(schemaName, parsed);
    return parsed;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new Error(`Schema file not found for \"${schemaName}\" at ${schemaPath}`);
    }
    throw error;
  }
}

async function loadValidator(schemaName: string): Promise<Ajv.ValidateFunction> {
  const cached = validatorCache.get(schemaName);
  if (cached) {
    return cached;
  }
  const schema = await loadSchema(schemaName);
  const validator = ajv.compile(schema);
  validatorCache.set(schemaName, validator);
  return validator;
}

function valueAtPath(payload: unknown, instancePath: string): unknown {
  if (!instancePath) {
    return payload;
  }
  const segments = instancePath
    .split("/")
    .filter(Boolean)
    .map((segment) => segment.replace(/~1/g, "/").replace(/~0/g, "~"));
  let current: any = payload; // eslint-disable-line @typescript-eslint/no-explicit-any -- required for traversal
  for (const segment of segments) {
    if (current == null) {
      return undefined;
    }
    const key = Number.isNaN(Number(segment)) ? segment : Number(segment);
    current = current[key as keyof typeof current];
  }
  return current;
}

function formatErrorMessage(schemaName: string, errors: ReadonlyArray<DefinedError>, payload: unknown): string {
  const header = `Schema validation failed for \"${schemaName}\"`;
  const details = errors.map((error) => formatSingleError(error, payload)).join("\n");
  return `${header}\n${details}`;
}

function formatSingleError(error: DefinedError, payload: unknown): string {
  const pathLabel = error.instancePath ? error.instancePath : "/";
  const actualValue = valueAtPath(payload, error.instancePath);
  const params = Object.entries(error.params)
    .map(([key, value]) => `${key}: ${inspect(value)}`)
    .join(", ");
  const paramsSuffix = params ? ` (${params})` : "";
  const message = error.message ?? "did not satisfy schema";
  const received = inspect(actualValue, { depth: 4, maxArrayLength: 10 });
  return ` - ${pathLabel} ${message}${paramsSuffix}. Received: ${received}`;
}

export async function schemaValidate(schemaName: string, payload: unknown): Promise<void> {
  const validator = await loadValidator(schemaName);
  const valid = validator(payload);
  if (!valid) {
    const errors = (validator.errors ?? []) as DefinedError[];
    throw new SchemaValidationError(schemaName, errors, payload);
  }
}
