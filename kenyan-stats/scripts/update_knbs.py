"""Safely refresh KNBS inflation from official HTTPS sources.

Primary: KNBS report listing. Fallback: official KNBS CPI Explorer.
Never disables TLS verification and never overwrites contradictory historic data.
"""
import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
LISTING = 'https://www.knbs.or.ke/reports_category/cpi-and-inflation-rates/'
EXPLORER = 'https://cpiexplorer.knbs.or.ke/'
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
               'August', 'September', 'October', 'November', 'December']
MONTHS = {name.lower(): i for i, name in enumerate(MONTH_NAMES, 1)}
REPORT_RE = re.compile(r'consumer-price-indices-and-inflation-rates-([a-z]+)-(20\d\d)/?$', re.I)
ANNUAL_RE = re.compile(r'annual\s+consumer\s+price\s+inflation\s+was\s+([0-9]+(?:\.[0-9]+)?)\s*per\s*cent', re.I)
ALTERNATE_RE = re.compile(r'annual\s+consumer\s+price\s+inflation\s+(?:stood|stands)\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*per\s*cent', re.I)


def discover_latest(html):
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    for a in soup.select('a[href]'):
        url = urljoin(LISTING, a['href'])
        parts = urlparse(url)
        if parts.scheme != 'https' or parts.hostname not in ('knbs.or.ke', 'www.knbs.or.ke'):
            continue
        match = REPORT_RE.search(parts.path)
        if not match or match.group(1).lower() not in MONTHS:
            continue
        year, month = int(match.group(2)), MONTHS[match.group(1).lower()]
        if date(year, month, 1) <= date.today().replace(day=1):
            matches.append((year, month, url))
    if not matches:
        raise ValueError('No dated KNBS CPI report links found')
    year, month = max((y, m) for y, m, _ in matches)
    urls = {u for y, m, u in matches if (y, m) == (year, month)}
    if len(urls) != 1:
        raise ValueError('Multiple links for newest CPI report')
    return year, month, urls.pop()


def parse_report(html, year, month, url):
    if not url.startswith('https://www.knbs.or.ke/reports/'):
        raise ValueError('Unexpected report URL')
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = ' '.join(soup.stripped_strings)
    expected = f'Consumer Price Indices and Inflation Rates – {MONTH_NAMES[month - 1]} {year}'
    headings = ' '.join(h.get_text(' ', strip=True) for h in soup.find_all(['h1', 'h2']))
    normalize = lambda s: re.sub(r'\s+', ' ', s).replace('—', '–').replace('-', '–').casefold()
    if normalize(expected) not in normalize(headings):
        raise ValueError('KNBS report heading does not match requested month')
    overview = re.search(r'\bOverview\b(.{0,2500})', text, re.I)
    if not overview:
        raise ValueError('Missing report overview')
    matches = ANNUAL_RE.findall(overview.group(1)) or ALTERNATE_RE.findall(overview.group(1))
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous annual inflation rate')
    annual = float(matches[0])
    if not 0 <= annual <= 100:
        raise ValueError('Implausible annual inflation')
    return {'period': f'{year}-{month:02d}', 'annual_inflation_pct': annual, 'report_url': url}


def parse_explorer(html):
    """Parse dated YoY headline, not the CPI level or month-on-month percentage.

    Converts KNBS Explorer's two-decimal YoY to the one-decimal reporting
    precision used by the existing KNBS release dataset.
    """
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = ' '.join(soup.stripped_strings)
    # Explicitly scope to the Inflation (YoY) label and its following month.
    pattern = (r'Inflation\s*\(\s*YoY\s*\)\s*'
               r'([0-9]{1,2}(?:\.[0-9]{1,3})?)\s*%\s*'
               r'(' + '|'.join(MONTH_NAMES) + r')\s+(20\d{2})\b')
    matches = re.findall(pattern, text, flags=re.I)
    if len(matches) != 1:
        raise ValueError('CPI Explorer YoY rate and reporting month not unambiguous')
    rate_str, month_str, year_str = matches[0]
    rate = float(rate_str)
    year, month = int(year_str), MONTHS[month_str.lower()]
    if not 0 <= rate <= 100 or date(year, month, 1) > date.today().replace(day=1):
        raise ValueError('Implausible or future CPI Explorer observation')
    # One decimal = precision of KNBS report summaries; avoids false
    # conflict between 6.76% dashboard and 6.8% report summary.
    from decimal import Decimal, ROUND_HALF_UP
    rounded = float(Decimal(rate_str).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
    return {'period': f'{year}-{month:02d}', 'annual_inflation_pct': rounded,
            'report_url': EXPLORER}


def update_data(old, observation):
    history = old.get('history', []) if old else []
    if not isinstance(history, list):
        raise ValueError('Invalid saved history')
    by_period = {}
    for item in history:
        if not isinstance(item, dict) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', item.get('period', '')):
            raise ValueError('Corrupted historical observation')
        if item['period'] in by_period:
            raise ValueError('Duplicate historical period')
        by_period[item['period']] = item
    period = observation['period']
    if period in by_period and by_period[period]['annual_inflation_pct'] != observation['annual_inflation_pct']:
        raise ValueError('Conflicting KNBS inflation figure; manual review required')
    if by_period and period < max(by_period):
        raise ValueError('Source older than latest saved observation')
    if period not in by_period:
        by_period[period] = observation
    return [by_period[k] for k in sorted(by_period)][-36:]


def fetch_html(session, url):
    response = session.get(url, timeout=35, headers={'User-Agent': 'KenyaInNumbers/0.4 public-statistics importer'})
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type', ''):
        raise ValueError('Expected HTML from official KNBS service')
    return response.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--listing-html', type=Path)
    parser.add_argument('--report-html', type=Path)
    parser.add_argument('--explorer-html', type=Path,
                        help='Parse a saved official CPI Explorer HTML fixture')
    parser.add_argument('--output', type=Path, default=ROOT / 'site/data/inflation.json')
    args = parser.parse_args()
    if bool(args.listing_html) != bool(args.report_html):
        parser.error('Provide both listing and report fixtures')
    if args.explorer_html and args.listing_html:
        parser.error('Choose report fixtures or Explorer fixture')
    if args.explorer_html:
        observation = parse_explorer(args.explorer_html.read_text(encoding='utf-8'))
    elif args.listing_html:
        year, month, url = discover_latest(args.listing_html.read_text(encoding='utf-8'))
        observation = parse_report(args.report_html.read_text(encoding='utf-8'), year, month, url)
    else:
        session = requests.Session()
        try:
            year, month, url = discover_latest(fetch_html(session, LISTING))
            observation = parse_report(fetch_html(session, url), year, month, url)
            print('KNBS report feed verified')
        except (requests.RequestException, ValueError) as err:
            print(f'KNBS report feed unavailable: {err}; trying official CPI Explorer')
            try:
                observation = parse_explorer(fetch_html(session, EXPLORER))
                print('KNBS CPI Explorer fallback verified')
            except (requests.RequestException, ValueError) as fallback_err:
                raise RuntimeError('Neither official KNBS HTTPS feed is usable. '
                                   'Existing verified data retained. '
                                   f'Report: {err}; Explorer: {fallback_err}') from fallback_err
    old = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
    history = update_data(old, observation)
    if history == old.get('history'):
        print('KNBS inflation unchanged; retaining saved dataset')
        return
    payload = {'schema_version': 1,
               'source': {'name': 'Kenya National Bureau of Statistics',
                          'url': observation['report_url']},
               'fetched_at': datetime.now(timezone.utc).isoformat(), 'history': history}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=args.output.parent, delete=False, encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
        temp = f.name
    os.replace(temp, args.output)
    print('Saved KNBS inflation', observation['period'], observation['annual_inflation_pct'])


if __name__ == '__main__':
    main()
