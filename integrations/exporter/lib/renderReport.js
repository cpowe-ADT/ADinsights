const fs = require('fs/promises');
const path = require('path');

const TEMPLATE_REPORT_PATH = path.join(__dirname, '..', 'templates', 'report.html');
const TEMPLATE_META_PAGES_V1_PATH = path.join(__dirname, '..', 'templates', 'meta_pages_v1.html');
const TEMPLATE_REPORT_V1_SNAPSHOT_PATH = path.join(
  __dirname,
  '..',
  'templates',
  'report_v1_snapshot.html',
);

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderKpiCard(kpi) {
  const label = escapeHtml(kpi.label ?? 'KPI');
  const value = escapeHtml(kpi.value ?? '—');
  const change = escapeHtml(kpi.change ?? '');

  return `\n      <article class="kpi-card">\n        <h2>${label}</h2>\n        <div class="value">${value}</div>\n        <div class="change">${change}</div>\n      </article>`;
}

function renderTableRow(row) {
  const cells = [
    row.channel,
    row.campaign,
    row.impressions,
    row.clicks,
    row.ctr,
    row.spend,
    row.conversions,
    row.cpa,
  ].map((value) => `          <td>${escapeHtml(value ?? '—')}</td>`);

  return ['        <tr>', ...cells, '        </tr>'].join('\n');
}

function renderMetaPagesKpiCard(kpi) {
  const label = escapeHtml(kpi.label ?? 'KPI');
  const rangeValue = escapeHtml(kpi.rangeValue ?? '—');
  const lastDayValue = escapeHtml(kpi.lastDayValue ?? '—');

  return `\n      <article class="card">\n        <h2>${label}</h2>\n        <div class="kpi-values">\n          <div>\n            <div class="label">Range</div>\n            <div class="value">${rangeValue}</div>\n          </div>\n          <div>\n            <div class="label">Last day</div>\n            <div class="value">${lastDayValue}</div>\n          </div>\n        </div>\n      </article>`;
}

function renderTrendSvg(points) {
  if (!Array.isArray(points) || points.length === 0) {
    return '';
  }
  const numeric = points
    .map((point) => ({
      date: point.date,
      value: typeof point.value === 'number' ? point.value : null,
    }))
    .filter((point) => point.value !== null);
  if (numeric.length === 0) {
    return '';
  }

  const values = numeric.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 640;
  const height = 120;
  const padding = 8;
  const range = max - min || 1;

  const toX = (index) =>
    padding + (index / Math.max(1, numeric.length - 1)) * (width - padding * 2);
  const toY = (value) => padding + (1 - (value - min) / range) * (height - padding * 2);

  const polyline = numeric
    .map((point, index) => `${toX(index).toFixed(1)},${toY(point.value).toFixed(1)}`)
    .join(' ');

  return [
    `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Trend chart">`,
    '<defs>',
    '  <linearGradient id="lineFade" x1="0" y1="0" x2="0" y2="1">',
    '    <stop offset="0%" stop-color="#0b69a3" stop-opacity="0.25" />',
    '    <stop offset="100%" stop-color="#0b69a3" stop-opacity="0.02" />',
    '  </linearGradient>',
    '</defs>',
    `<polyline fill="none" stroke="#0b69a3" stroke-width="3" points="${polyline}" />`,
    '</svg>',
  ].join('\n');
}

function renderMetaPostRow(row) {
  const created = escapeHtml(row.createdTime ?? '—');
  const mediaType = escapeHtml(row.mediaType ?? '—');
  const snippet = escapeHtml(row.messageSnippet ?? '—');
  const metricValue = escapeHtml(row.metricValue ?? '—');
  const permalink = row.permalink ? String(row.permalink) : '';
  const linkCell = permalink ? `<a href="${escapeHtml(permalink)}">Open</a>` : '—';

  return [
    '        <tr>',
    `          <td>${created}</td>`,
    `          <td>${mediaType}</td>`,
    `          <td class="snippet">${snippet}</td>`,
    `          <td>${metricValue}</td>`,
    `          <td>${linkCell}</td>`,
    '        </tr>',
  ].join('\n');
}

function renderReportV1KpiCard(kpi) {
  const label = escapeHtml(kpi.label ?? 'Metric');
  const value = escapeHtml(kpi.value ?? '—');
  const context = escapeHtml(kpi.context ?? '');

  return `\n      <article class="metric-card">\n        <h2>${label}</h2>\n        <div class="value">${value}</div>\n        <div class="context">${context}</div>\n      </article>`;
}

function renderReportV1Row(row) {
  const cells = [row.page, row.widget, row.metric, row.value, row.status, row.note].map(
    (value) => `          <td>${escapeHtml(value ?? '—')}</td>`,
  );

  return ['        <tr>', ...cells, '        </tr>'].join('\n');
}

function renderReportV1Warning(warning) {
  return `<li>${escapeHtml(warning)}</li>`;
}

function renderReportV1AvailabilityNotes(warnings) {
  const warningItems = warnings.map(renderReportV1Warning).join('\n');
  return warningItems
    ? `<section class="availability-notes"><h2>Data availability notes</h2><ul>${warningItems}</ul></section>`
    : '';
}

function reportV1Number(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatReportV1Value(value, options = {}) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  const number = reportV1Number(value);
  if (number !== null && (typeof value === 'number' || options.format || options.yFormat)) {
    const numberOptions = Number.isInteger(number)
      ? { maximumFractionDigits: 0 }
      : { maximumFractionDigits: 2 };
    const formatted = new Intl.NumberFormat('en-US', numberOptions).format(number);
    if (options.format === 'currency' || options.yFormat === 'currency') {
      return [options.currency, formatted].filter(Boolean).join(' ');
    }
    if (options.format === 'rate' || options.yFormat === 'percent') {
      return `${formatted}%`;
    }
    return formatted;
  }
  return String(value);
}

function reportV1PositiveInt(value, fallback, { min = 1, max = 48 } = {}) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function reportV1LayoutConfig(reportLayout) {
  if (!reportLayout || typeof reportLayout !== 'object') {
    return null;
  }
  const config =
    reportLayout.config && typeof reportLayout.config === 'object'
      ? reportLayout.config
      : reportLayout;
  if (!Array.isArray(config.widgets)) {
    return null;
  }
  return config;
}

function renderReportV1SavedLayout(reportLayout) {
  const config = reportV1LayoutConfig(reportLayout);
  if (!config) {
    return '';
  }
  const cols = reportV1PositiveInt(config.cols, 12, { min: 1, max: 24 });
  const rowHeight = reportV1PositiveInt(config.rowHeight, 64, { min: 32, max: 160 });
  const widgets = [...config.widgets]
    .filter((widget) => widget && typeof widget === 'object')
    .sort(
      (a, b) => (Number(a.y) || 0) - (Number(b.y) || 0) || (Number(a.x) || 0) - (Number(b.x) || 0),
    );
  const cells = widgets.map((widget) => renderReportV1LayoutWidget(widget, rowHeight)).join('\n');
  const title = escapeHtml(config.title ?? 'Saved report layout');
  return [
    `<section class="saved-layout" aria-label="${title}" style="grid-template-columns: repeat(${cols}, minmax(0, 1fr)); grid-auto-rows: ${rowHeight}px;">`,
    cells || '<p class="muted">Saved layout has no widgets.</p>',
    '</section>',
  ].join('\n');
}

function renderReportV1LayoutWidget(widget, rowHeight) {
  const x = reportV1PositiveInt(widget.x, 1, { max: 24 });
  const y = reportV1PositiveInt(widget.y, 1, { max: 200 });
  const w = reportV1PositiveInt(widget.w, 12, { max: 24 });
  const h = reportV1PositiveInt(widget.h, 2, { max: 24 });
  const type = String(widget.type ?? 'note');
  const title = escapeHtml(widget.title ?? widget.id ?? 'Widget');
  const body = renderReportV1LayoutWidgetBody(widget, type);
  return [
    `<article class="saved-layout__cell saved-layout__cell--${escapeHtml(type)}" data-widget-id="${escapeHtml(widget.id ?? '')}" style="grid-column: ${x} / span ${w}; grid-row: ${y} / span ${h}; min-height: ${Math.max(80, h * rowHeight)}px;">`,
    `<h2>${title}</h2>`,
    body,
    '</article>',
  ].join('\n');
}

function renderReportV1LayoutWidgetBody(widget, type) {
  const options = widget.options && typeof widget.options === 'object' ? widget.options : {};
  if (type === 'kpi' || type === 'gauge') {
    const value = formatReportV1Value(widget.data, options);
    const context = type === 'gauge' && options.max ? `of ${formatReportV1Value(options.max)}` : '';
    return [
      `<div class="saved-layout__value">${escapeHtml(value)}</div>`,
      context ? `<div class="saved-layout__context">${escapeHtml(context)}</div>` : '',
    ].join('\n');
  }
  if (type === 'note') {
    return `<p class="saved-layout__note">${escapeHtml(options.text ?? '')}</p>`;
  }
  if (type === 'table') {
    return renderReportV1LayoutTable(widget.data, options);
  }
  if (type === 'bar' || type === 'pie') {
    return renderReportV1LayoutBars(widget.data, options);
  }
  if (type === 'line') {
    return renderReportV1LayoutLine(widget.data, options);
  }
  return `<p class="saved-layout__note">Unsupported widget type: ${escapeHtml(type)}</p>`;
}

function renderReportV1LayoutTable(data, options = {}) {
  const rows = Array.isArray(data) ? data.filter((row) => row && typeof row === 'object') : [];
  const columns =
    Array.isArray(options.columns) && options.columns.length
      ? options.columns
      : Object.keys(rows[0] ?? {}).map((key) => ({ key, header: key.replace(/_/g, ' ') }));
  const header = columns
    .map((column) => `<th>${escapeHtml(column.header ?? column.key ?? '')}</th>`)
    .join('');
  const body = rows
    .slice(0, 12)
    .map((row) => {
      const cells = columns
        .map((column) => {
          const key = column.key;
          return `<td>${escapeHtml(formatReportV1Value(row[key]))}</td>`;
        })
        .join('');
      return `<tr>${cells}</tr>`;
    })
    .join('');
  return [
    '<div class="saved-layout__table-wrap"><table class="saved-layout__table">',
    `<thead><tr>${header}</tr></thead>`,
    `<tbody>${body || `<tr><td colspan="${Math.max(columns.length, 1)}">No rows</td></tr>`}</tbody>`,
    '</table></div>',
  ].join('\n');
}

function renderReportV1LayoutBars(data, options = {}) {
  const rows = Array.isArray(data) ? data.filter((row) => row && typeof row === 'object') : [];
  const numericValues = rows
    .map((row) => reportV1Number(row.value))
    .filter((value) => value !== null);
  const max = Math.max(...numericValues, 0) || 1;
  const bars = rows
    .slice(0, 10)
    .map((row) => {
      const value = reportV1Number(row.value);
      const width = value === null ? 0 : Math.max(2, Math.min(100, (value / max) * 100));
      return [
        '<div class="saved-layout__bar-row">',
        `<span>${escapeHtml(row.label ?? 'Unspecified')}</span>`,
        `<div class="saved-layout__bar-track"><div style="width: ${width.toFixed(1)}%"></div></div>`,
        `<strong>${escapeHtml(formatReportV1Value(row.value, options))}</strong>`,
        '</div>',
      ].join('');
    })
    .join('\n');
  return bars || '<p class="saved-layout__note">No chart rows</p>';
}

function renderReportV1LayoutLine(data, options = {}) {
  const rows = Array.isArray(data) ? data.filter((row) => row && typeof row === 'object') : [];
  const series = Array.isArray(options.series) ? options.series : [];
  const firstKey =
    series[0]?.key || Object.keys(rows[0] ?? {}).find((key) => key !== 'date') || 'value';
  const points = rows.map((row) => ({
    date: row.date,
    value: reportV1Number(row[firstKey]),
  }));
  const svg = renderTrendSvg(points);
  const label = series[0]?.label || firstKey.replace(/_/g, ' ');
  return [
    svg || '<p class="saved-layout__note">No trend points</p>',
    `<div class="saved-layout__context">${escapeHtml(label)}</div>`,
  ].join('\n');
}

async function renderReport(data = {}) {
  const templateKey = String(data.template ?? '').trim();
  let template;
  if (templateKey === 'meta_pages_v1') {
    template = await fs.readFile(TEMPLATE_META_PAGES_V1_PATH, 'utf8');
  } else if (templateKey === 'report_v1_snapshot') {
    template = await fs.readFile(TEMPLATE_REPORT_V1_SNAPSHOT_PATH, 'utf8');
  } else {
    template = await fs.readFile(TEMPLATE_REPORT_PATH, 'utf8');
  }

  if (templateKey === 'meta_pages_v1') {
    const kpiSummary = (data.kpis ?? []).map(renderMetaPagesKpiCard).join('\n');
    const trendTitle = escapeHtml(data.trend?.title ?? 'Trend');
    const trendNote = escapeHtml(data.trend?.note ?? '');
    const trendRange = escapeHtml(data.trend?.rangeLabel ?? '');
    const svg = renderTrendSvg(data.trend?.points ?? []);
    const trendBody = svg ? svg : '<div class="empty">No trend points available.</div>';

    const topPostsTitle = escapeHtml(data.topPosts?.title ?? 'Top posts');
    const topPostsMetric = escapeHtml(data.topPosts?.metricLabel ?? 'Metric');
    const topPostRows = (data.topPosts?.rows ?? []).map(renderMetaPostRow).join('\n');

    const replacements = {
      '{{TITLE}}': escapeHtml(data.title ?? 'Facebook Page Insights'),
      '{{SUBTITLE}}': escapeHtml(data.subtitle ?? ''),
      '{{DATE_RANGE}}': escapeHtml(data.dateRange ?? ''),
      '{{GENERATED_AT}}': escapeHtml(data.generatedAt ?? ''),
      '{{KPI_SUMMARY}}': kpiSummary || '<p class="muted">No KPI data provided.</p>',
      '{{TREND_TITLE}}': trendTitle,
      '{{TREND_NOTE}}': trendNote,
      '{{TREND_RANGE}}': trendRange,
      '{{TREND_BODY}}': trendBody,
      '{{TOP_POSTS_TITLE}}': topPostsTitle,
      '{{TOP_POSTS_METRIC}}': topPostsMetric,
      '{{TOP_POST_ROWS}}':
        topPostRows || '        <tr><td colspan="5">No posts available.</td></tr>',
    };

    return Object.entries(replacements).reduce(
      (html, [token, value]) => html.replace(new RegExp(token, 'g'), value),
      template,
    );
  }

  if (templateKey === 'report_v1_snapshot') {
    const kpiSummary = (data.kpis ?? []).map(renderReportV1KpiCard).join('\n');
    const reportRows = (data.rows ?? []).map(renderReportV1Row).join('\n');
    const warningBlock = renderReportV1AvailabilityNotes(data.warnings ?? []);
    const savedLayout = renderReportV1SavedLayout(data.reportLayout);
    const fallbackBody = [
      `<section class="metric-grid">${kpiSummary || '<p class="muted">No KPI metrics provided.</p>'}</section>`,
      warningBlock,
      '<section>',
      '<table>',
      '<thead>',
      '<tr>',
      '<th style="width: 18%">Page</th>',
      '<th style="width: 18%">Widget</th>',
      '<th style="width: 18%">Metric</th>',
      '<th style="width: 12%">Value</th>',
      '<th style="width: 12%">Status</th>',
      '<th>Note</th>',
      '</tr>',
      '</thead>',
      '<tbody>',
      reportRows || '        <tr><td colspan="6">No report rows available.</td></tr>',
      '</tbody>',
      '</table>',
      '</section>',
    ].join('\n');
    const reportBody = savedLayout
      ? [warningBlock, savedLayout].filter(Boolean).join('\n')
      : fallbackBody;

    const replacements = {
      '{{TITLE}}': escapeHtml(data.title ?? 'Report snapshot'),
      '{{SUBTITLE}}': escapeHtml(data.subtitle ?? ''),
      '{{DATE_RANGE}}': escapeHtml(data.dateRange ?? ''),
      '{{GENERATED_AT}}': escapeHtml(data.generatedAt ?? ''),
      '{{REPORT_BODY}}': reportBody,
    };

    return Object.entries(replacements).reduce(
      (html, [token, value]) => html.replace(new RegExp(token, 'g'), value),
      template,
    );
  }

  const kpiSummary = (data.kpis ?? []).map(renderKpiCard).join('\n');
  const tableRows = (data.rows ?? []).map(renderTableRow).join('\n');

  const replacements = {
    '{{TITLE}}': escapeHtml(data.title ?? 'Performance Report'),
    '{{DATE_RANGE}}': escapeHtml(data.dateRange ?? ''),
    '{{KPI_SUMMARY}}': kpiSummary || '<p>No KPI data provided.</p>',
    '{{TABLE_ROWS}}':
      tableRows || '        <tr><td colspan="8">No tabular data provided.</td></tr>',
  };

  return Object.entries(replacements).reduce(
    (html, [token, value]) => html.replace(new RegExp(token, 'g'), value),
    template,
  );
}

module.exports = {
  renderReport,
};
