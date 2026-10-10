'use strict';
(async function loadCBK() {
  const status = document.getElementById('cbk-status');
  const target = document.getElementById('cbk-values');
  const date = document.getElementById('cbk-date');
  if (!status || !target || !date) return;
  try {
    const response = await fetch('./data/exchange-rates.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error('CBK data not published yet: HTTP ' + response.status);
    const data = await response.json();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(data.date || '')) throw new Error('Invalid date');
    for (const code of ['USD', 'GBP', 'EUR']) {
      const value = data.rates?.[code];
      if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) throw new Error('Invalid ' + code);
    }
    const formatter = new Intl.NumberFormat('en-KE', {minimumFractionDigits: 2, maximumFractionDigits: 4});
    for (const [code, name] of [['USD', 'US dollar'], ['GBP', 'British pound'], ['EUR', 'Euro']]) {
      const wrapper = document.createElement('div');
      const label = document.createElement('dt');
      const amount = document.createElement('dd');
      label.textContent = name + ' (1 ' + code + ')';
      amount.textContent = 'KES ' + formatter.format(data.rates[code]);
      wrapper.append(label, amount);
      target.append(wrapper);
    }
    date.textContent = 'CBK published: ' + data.date;
    status.textContent = 'Official CBK indicative rates (not transaction quotes).';
  } catch (error) {
    status.textContent = 'CBK data not available yet; consult the official source.';
    console.error(error);
  }
})();
