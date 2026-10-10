"""Update Kenya in Numbers from KNBS monthly CPI report summaries.

Uses official KNBS HTML reports (not PDFs) and fails closed on source layout changes.
Keeps historical observations and refuses to overwrite a published month with
contradictory figures. Updating a figure requires a reviewed manual intervention.
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
MONTHS = {name.lower(): i for i, name in enumerate([
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'], 1)}
REPORT_RE = re.compile(r'consumer-price-indices-and-inflation-rates-([a-z]+)-(20\d\d)/?$', re.I)
ANNUAL_RE = re.compile(r'annual\s+consumer\s+price\s+inflation\s+was\s+([0-9]+(?:\.[0-9]+)?)\s*per\s*cent', re.I)
ALTERNATE_RE = re.compile(r'annual\s+consumer\s+price\s+inflation\s+(?:stood|stands)\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*per\s*cent', re.I)


def discover_latest(html):
    """Find the most recent report only on the official KNBS reports category page."""
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    for a in soup.select('a[href]'):
        url = urljoin(LISTING, a.get('href', ''))
        parts = urlparse(url)
        if parts.hostname not in ('knbs.or.ke', 'www.knbs.or.ke'):
            continue
        match = REPORT_RE.search(parts.path)
        if not match or match.group(1).lower() not in MONTHS:
            continue
        month, year = MONTHS[match.group(1).lower()], int(match.group(2))
        if date(year, month, 1) > date.today().replace(day=1):
            continue
        matches.append((year, month, url))
    if not matches:
        raise ValueError('No dated KNBS CPI report links found')
    latest = max((y, m) for y, m, _ in matches)
    urls = {u for y, m, u in matches if (y, m) == latest}
    if len(urls) != 1:
        raise ValueError('Multiple links for newest CPI report')
    return latest[0], latest[1], urls.pop()


def parse_report(html, year, month, url):
    if not url.startswith('https://www.knbs.or.ke/reports/'):
        raise ValueError('Unexpected report URL')
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = ' '.join(soup.stripped_strings)
    expected_title = f'Consumer Price Indices and Inflation Rates – {list(MONTHS)[month-1].title()} {year}'
    # HTML title or heading must match the expected report month.
    headings = ' '.join(h.get_text(' ', strip=True) for h in soup.find_all(['h1', 'h2']))
    normalized = lambda s: re.sub(r'\s+', ' ', s).replace('—', '–').replace('-', '–').casefold()
    if normalized(expected_title) not in normalized(headings):
        raise ValueError('KNBS report heading does not match requested month')
    overview = re.search(r'\bOverview\b(.{0,2500})', text, re.I)
    if not overview:
        raise ValueError('Missing report overview')
    summary = overview.group(1)
    matches = ANNUAL_RE.findall(summary) or ALTERNATE_RE.findall(summary)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous KNBS annual inflation rate')
    annual = float(matches[0])
    if not 0 <= annual <= 100:
        raise ValueError('Implausible annual inflation')
    if f'{year}' not in text:
        raise ValueError('Missing reporting year')
    return {'period': f'{year}-{month:02d}', 'annual_inflation_pct': annual, 'report_url': url}


def update_data(old, observation):
    history = old.get('history', []) if old else []
    if not isinstance(history, list):
        raise ValueError('Invalid saved KNBS history')
    by_period = {}
    for item in history:
        if not isinstance(item, dict) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', item.get('period', '')):
            raise ValueError('Corrupted saved historical observation')
        if item['period'] in by_period:
            raise ValueError('Duplicate historical period')
        by_period[item['period']] = item
    period = observation['period']
    if period in by_period and by_period[period]['annual_inflation_pct'] != observation['annual_inflation_pct']:
        raise ValueError('KNBS rate changed for an existing period; manual review required')
    if by_period and period < max(by_period):
        raise ValueError('Source is older than the latest saved KNBS observation')
    if period not in by_period:
        by_period[period] = observation
    result = [by_period[k] for k in sorted(by_period)][-36:]
    return result


def fetch_html(session, url):
    response = session.get(url, timeout=45, headers={'User-Agent': 'KenyaInNumbers/0.3 public-statistics importer'})
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type', ''):
        raise ValueError('KNBS did not return HTML')
    return response.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--listing-html', type=Path, help='Local listing fixture for testing')
    parser.add_argument('--report-html', type=Path, help='Local report fixture for testing')
    parser.add_argument('--output', type=Path, default=ROOT / 'site/data/inflation.json')
    args = parser.parse_args()
    if bool(args.listing_html) != bool(args.report_html):
        parser.error('Provide both --listing-html and --report-html, or neither')
    session = requests.Session()
    listing = args.listing_html.read_text(encoding='utf-8') if args.listing_html else fetch_html(session, LISTING)
    year, month, url = discover_latest(listing)
    report = args.report_html.read_text(encoding='utf-8') if args.report_html else fetch_html(session, url)
    observation = parse_report(report, year, month, url)
    old = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
    history = update_data(old, observation)
    if history == old.get('history'):
        print('KNBS inflation unchanged; no write needed')
        return
    payload = {'schema_version': 1, 'source': {'name': 'Kenya National Bureau of Statistics', 'url': LISTING},
               'fetched_at': datetime.now(timezone.utc).isoformat(), 'history': history}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=args.output.parent, delete=False, encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
        path = f.name
    os.replace(path, args.output)
    print('Saved KNBS inflation for', observation['period'], 'at', observation['annual_inflation_pct'], '%')


if __name__ == '__main__':
    main()
