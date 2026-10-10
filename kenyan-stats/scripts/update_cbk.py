"""Import dated USD, GBP, EUR indicative rates from CBK's official forex summary.

Fails closed on ambiguous formatting, missing currencies or invalid publication dates.
"""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://www.centralbank.go.ke/forex/'
CURRENCIES = {'USD': 'US DOLLAR', 'GBP': 'STG POUND', 'EUR': 'EURO'}


def parse_rates(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = ' '.join(soup.stripped_strings)
    # The forex summary includes a daily currency card and a dated publication label.
    portions = re.split(r'Daily KES Exchange Rates', text, flags=re.IGNORECASE)
    if len(portions) < 2:
        raise ValueError('CBK daily rates section not found')
    candidates = []
    for portion in portions[1:]:
        # Only inspect the short summary immediately following its heading.
        summary = portion[:1000]
        match = re.search(r'Posted\s+On\s*:\s*(\d{2}[-/]\d{2}[-/]\d{4})', summary, re.I)
        if not match:
            continue
        published = datetime.strptime(match.group(1).replace('/', '-'), '%d-%m-%Y').date()
        rates = {}
        for code, label in CURRENCIES.items():
            matches = re.findall(r'\b' + re.escape(label) + r'\s*:?\s*([\d,]+\.\d{2,6})\b', summary[:match.start()], re.I)
            if len(matches) != 1:
                raise ValueError(f'Missing or ambiguous CBK {code} rate')
            value = float(matches[0].replace(',', ''))
            if not (20 < value < 1000):
                raise ValueError(f'Implausible CBK {code} value')
            rates[code] = value
        if published > date.today():
            raise ValueError('CBK publication date is in the future')
        candidates.append((published, rates))
    if len(candidates) != 1:
        raise ValueError('Could not unambiguously identify dated CBK rates')
    published, rates = candidates[0]
    return {'date': published.isoformat(), 'rates': rates}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--html', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'site/data/exchange-rates.json')
    args = parser.parse_args()
    if args.html:
        html = args.html.read_text(encoding='utf-8')
    else:
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'KenyaInNumbers/0.2 public-statistics updater'})
        response.raise_for_status()
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML from CBK')
        html = response.text
    parsed = parse_rates(html)
    if args.output.exists():
        old = json.loads(args.output.read_text(encoding='utf-8'))
        if old.get('date', '') > parsed['date']:
            raise ValueError('CBK source older than saved data')
        if old.get('date') == parsed['date'] and old.get('rates') == parsed['rates']:
            print('No CBK changes')
            return
    payload = {'schema_version': 1, 'source': {'name': 'Central Bank of Kenya', 'url': SOURCE},
               'date': parsed['date'], 'rates': parsed['rates'], 'fetched_at': datetime.now(timezone.utc).isoformat()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=args.output.parent, delete=False, encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
        temp_path = f.name
    os.replace(temp_path, args.output)
    print('Saved CBK indicative rates for', parsed['date'])


if __name__ == '__main__':
    main()
