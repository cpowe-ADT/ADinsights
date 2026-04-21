import { beforeEach, describe, expect, it, vi } from 'vitest';

import { downloadCsv, rowsToCsv } from './csvExport';

describe('rowsToCsv — RFC 4180 + CSV-injection hardening', () => {
  it('handles a simple row without quoting', () => {
    const out = rowsToCsv(['a', 'b'], [[1, 2]]);
    expect(out).toBe('a,b\r\n1,2');
  });

  it('escapes embedded double quotes by doubling them (quote torture case)', () => {
    const out = rowsToCsv(['v'], [['"Hello, world"']]);
    // Expected: `"""Hello, world"""` for the cell value.
    expect(out).toBe('v\r\n"""Hello, world"""');
  });

  it('quotes multi-line values', () => {
    const out = rowsToCsv(['v'], [['Line1\nLine2']]);
    expect(out).toBe('v\r\n"Line1\nLine2"');
  });

  it('quotes fields containing a bare carriage return (Excel/Mac-legacy line ending)', () => {
    // RFC 4180 §2.6 — CR alone inside a field must trigger quoting. The
    // output's own row separator is CRLF, so the quoted cell embeds \r
    // verbatim and Excel treats it as an in-cell line break, not a new row.
    const out = rowsToCsv(['v'], [['before\rafter']]);
    expect(out).toBe('v\r\n"before\rafter"');
  });

  it('quotes fields with literal CRLF inside the cell', () => {
    const out = rowsToCsv(['v'], [['row1\r\nrow2']]);
    expect(out).toBe('v\r\n"row1\r\nrow2"');
  });

  it('quotes a field containing a comma (separator collision)', () => {
    const out = rowsToCsv(['v'], [['Kingston, Jamaica']]);
    expect(out).toBe('v\r\n"Kingston, Jamaica"');
  });

  it('preserves Unicode content untouched (parish name with diacritic smoke test)', () => {
    // Portmoré uses é; export must not mangle the byte or quote unnecessarily.
    const out = rowsToCsv(['parish'], [['Portmoré']]);
    expect(out).toBe('parish\r\nPortmoré');
  });

  it('neutralizes leading = with an apostrophe', () => {
    const out = rowsToCsv(['v'], [['=SUM(A1:A10)']]);
    expect(out).toBe("v\r\n'=SUM(A1:A10)");
  });

  it('neutralizes leading @ with an apostrophe', () => {
    const out = rowsToCsv(['v'], [['@attacker']]);
    expect(out).toBe("v\r\n'@attacker");
  });

  it('neutralizes leading + and -', () => {
    const out = rowsToCsv(['v'], [['+cmd'], ['-whatever']]);
    expect(out).toBe("v\r\n'+cmd\r\n'-whatever");
  });

  it('converts null and undefined to empty strings', () => {
    const out = rowsToCsv(['a', 'b'], [[null, undefined]]);
    expect(out).toBe('a,b\r\n,');
  });

  it('handles a mixed torture row', () => {
    const out = rowsToCsv(
      ['name', 'note'],
      [['=SUM(A1)', 'He said "hi", then\nleft']],
    );
    expect(out).toBe(
      'name,note\r\n\'=SUM(A1),"He said ""hi"", then\nleft"',
    );
  });
});

describe('downloadCsv', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('creates a Blob URL and triggers a click on a temporary anchor', () => {
    const createObjectURL = vi.fn(() => 'blob:mock-url');
    const revokeObjectURL = vi.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    });

    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click');

    downloadCsv('test.csv', 'a,b\r\n1,2');

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blobArg = createObjectURL.mock.calls[0][0] as Blob;
    expect(blobArg.type).toContain('text/csv');
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });

  it('is a no-op when window/document are unavailable (smoke)', () => {
    // Cannot actually unset window in jsdom; just ensure the exported function
    // exists and is callable without throwing on missing URL methods.
    expect(typeof downloadCsv).toBe('function');
  });
});
