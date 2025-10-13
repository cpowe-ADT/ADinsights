const fs = require('fs/promises');
const path = require('path');

const TEMPLATE_PATH = path.join(__dirname, '..', 'templates', 'report.html');

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

async function renderReport(data = {}) {
  const template = await fs.readFile(TEMPLATE_PATH, 'utf8');

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
