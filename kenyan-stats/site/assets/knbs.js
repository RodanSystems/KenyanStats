'use strict';
(async function loadKNBS() {
  const status = document.getElementById('knbs-status');
  const metric = document.getElementById('knbs-inflation');
  const period = document.getElementById('knbs-period');
  const source = document.getElementById('knbs-source');
  const chart = document.getElementById('knbs-history');
  if (!status || !metric || !period || !source || !chart) return;
  try {
    const response = await fetch('./data/inflation.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    if (!Array.isArray(data.history) || !data.history.length) throw new Error('No inflation records');
    const history = [...data.history].sort((a, b) => a.period.localeCompare(b.period));
    if (history.some(row => !/^20\d{2}-(0[1-9]|1[0-2])$/.test(row.period) ||
       !Number.isFinite(row.annual_inflation_pct) || row.annual_inflation_pct < 0 || row.annual_inflation_pct > 100 ||
       typeof row.report_url !== 'string' || !row.report_url.startsWith('https://www.knbs.or.ke/reports/'))) {
      throw new Error('Invalid inflation data');
    }
    const latest = history[history.length - 1];
    const prettyMonth = month => new Date(month + '-01T12:00:00Z').toLocaleDateString('en-KE', {month: 'long', year: 'numeric', timeZone: 'UTC'});
    metric.textContent = latest.annual_inflation_pct.toFixed(1) + '%';
    period.textContent = 'Annual inflation · ' + prettyMonth(latest.period);
    source.href = latest.report_url;
    status.textContent = 'Official KNBS annual consumer-price inflation (year-on-year).';
    chart.replaceChildren();
    if (history.length > 1) {
      for (const row of history.slice(-12)) {
        const wrapper = document.createElement('div');
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        dt.textContent = prettyMonth(row.period);
        dd.textContent = row.annual_inflation_pct.toFixed(1) + '%';
        wrapper.append(dt, dd);
        chart.append(wrapper);
      }
    }
  } catch (error) {
    status.textContent = 'KNBS inflation data not available; consult the official source.';
    console.error(error);
  }
})();
