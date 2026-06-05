/**
 * Manual CSV serializer (papaparse is NOT an installed dependency).
 *
 * Handles the three escape-worthy conditions required by RFC 4180 plus one
 * spreadsheet-safety hardening:
 *
 *   1. A field containing a comma, double-quote, carriage return, or newline
 *      is wrapped in double-quotes.
 *   2. Inside a quoted field, each `"` is doubled to `""`.
 *   3. A field whose first character is `=`, `+`, `-`, or `@` is prefixed with
 *      a single apostrophe (`'`) to prevent CSV-injection attacks in Excel /
 *      Google Sheets / LibreOffice (the apostrophe is stripped by the sheet
 *      renderer but blocks formula execution).
 *   4. `null` and `undefined` become empty strings.
 *
 * The CSV is emitted with CRLF line terminators per RFC 4180.
 */

export type CsvCell = string | number | null | undefined;

const CRLF = '\r\n';
const DANGEROUS_LEADING = new Set(['=', '+', '-', '@']);

const needsQuoting = (value: string): boolean =>
  value.includes(',') || value.includes('"') || value.includes('\n') || value.includes('\r');

const escapeCell = (cell: CsvCell): string => {
  if (cell === null || cell === undefined) {
    return '';
  }

  let raw = typeof cell === 'number' ? String(cell) : cell;

  // CSV-injection hardening: neutralize leading formula triggers.
  if (raw.length > 0 && DANGEROUS_LEADING.has(raw.charAt(0))) {
    raw = `'${raw}`;
  }

  if (needsQuoting(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }

  return raw;
};

/**
 * Serialize a header row plus body rows into an RFC-4180-compliant CSV string.
 */
export function rowsToCsv(headers: string[], rows: CsvCell[][]): string {
  const lines: string[] = [];
  lines.push(headers.map((h) => escapeCell(h)).join(','));
  for (const row of rows) {
    lines.push(row.map((cell) => escapeCell(cell)).join(','));
  }
  return lines.join(CRLF);
}

/**
 * Trigger a browser download of a CSV string. No-op outside the browser.
 *
 * The BOM prefix (`\uFEFF`) nudges Excel on Windows into treating the file as
 * UTF-8 so non-ASCII parish names render correctly.
 */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return;
  }

  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename || 'download.csv';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
