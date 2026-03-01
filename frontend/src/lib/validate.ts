import Ajv2020 from 'ajv/dist/2020.js';
import type { ErrorObject, ValidateFunction } from 'ajv';

import budgetSchema from '../schemas/budget.schema.json';
import creativeSchema from '../schemas/creative.schema.json';
import metricsSchema from '../schemas/metrics.schema.json';
import parishSchema from '../schemas/parish.schema.json';
import parishGeometrySchema from '../schemas/parish-geometry.schema.json';
import tenantsSchema from '../schemas/tenants.schema.json';

export type SchemaKey = 'metrics' | 'creative' | 'budget' | 'parish' | 'parishGeometry' | 'tenants';

type SchemaMap = Record<SchemaKey, ValidateFunction>;

const ajv = new Ajv2020({
  allErrors: true,
  strict: false,
  allowUnionTypes: true,
});

ajv.addFormat('date', /^\d{4}-\d{2}-\d{2}$/);
ajv.addFormat('uri', {
  type: 'string',
  validate: (value: string) => {
    try {
      const url = new URL(value);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
      return false;
    }
  },
});

const validators: SchemaMap = {
  metrics: ajv.compile(metricsSchema),
  creative: ajv.compile(creativeSchema),
  budget: ajv.compile(budgetSchema),
  parish: ajv.compile(parishSchema),
  parishGeometry: ajv.compile(parishGeometrySchema),
  tenants: ajv.compile(tenantsSchema),
};

const shouldValidate = import.meta.env.MODE === 'test' || import.meta.env.DEV;

function formatErrors(errors: ErrorObject[] | null | undefined): string {
  if (!errors?.length) {
    return '';
  }

  return errors
    .map((error) => {
      const instancePath = error.instancePath ? `${error.instancePath} ` : '';
      return `${instancePath}${error.message ?? 'is invalid'}`.trim();
    })
    .join('; ');
}

export function validate(schema: SchemaKey | undefined, payload: unknown): boolean {
  if (!schema || !shouldValidate) {
    return true;
  }

  const validator = validators[schema];
  const valid = validator(payload);

  if (!valid) {
    const message = formatErrors(validator.errors);
    console.warn(`Schema validation failed for "${schema}": ${message}`);
  }

  return valid;
}
