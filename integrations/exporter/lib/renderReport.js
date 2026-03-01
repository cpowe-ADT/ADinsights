const fs = require('fs/promises');
const path = require('path');

const TEMPLATE_REPORT_PATH = path.join(__dirname, '..', 'templates', 'report.html');
const TEMPLATE_META_PAGES_V1_PATH = path.join(
  __dirname,
  '..',
  'templates',
  'meta_pages_v1.html',
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
  const linkCell = permalink
    ? `<a href="${escapeHtml(permalink)}">Open</a>`
    : '—';

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

async function renderReport(data = {}) {
  const templateKey = String(data.template ?? '').trim();
  const template =
    templateKey === 'meta_pages_v1'
      ? await fs.readFile(TEMPLATE_META_PAGES_V1_PATH, 'utf8')
      : await fs.readFile(TEMPLATE_REPORT_PATH, 'utf8');

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
