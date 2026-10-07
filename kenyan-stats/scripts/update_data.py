"""Fetch EPRA's HTML table. Fail closed if the official format changes."""
import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://www.epra.go.ke/pump-prices"

def parse_date(value):
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date: {value!r}")

def parse_prices(html):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for index, row in enumerate(rows):
            headings = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).lower() for cell in row.find_all(["th", "td"])]
            def column(pattern):
                matches = [i for i,h in enumerate(headings) if re.search(pattern,h)]
                if len(matches)!=1:
                    raise ValueError("Missing or ambiguous header")
                return matches[0]
            try:
                cols = {"town":column(r"town"),"petrol":column(r"super|petrol"),"diesel":column(r"diesel"),"kerosene":column(r"kerosene"),"valid_from":column(r"start|from"),"valid_to":column(r"^to$|end|to date|date to")}
            except ValueError:
                continue
            for data_row in rows[index+1:]:
                cells = [cell.get_text(" ",strip=True) for cell in data_row.find_all("td")]
                if not cells:
                    continue
                if len(cells)<=max(cols.values()):
                    raise ValueError("Incomplete price row")
                item = {key:cells[pos] for key,pos in cols.items()}
                for key in ("valid_from","valid_to"):
                    item[key]=parse_date(item[key]).isoformat()
                if item["valid_from"]>item["valid_to"]:
                    raise ValueError("Reversed dates")
                for key in ("petrol","diesel","kerosene"):
                    item[key]=float(item[key].replace(",",""))
                    if not 0<item[key]<1000:
                        raise ValueError("Implausible price")
                if not item["town"]:
                    raise ValueError("Missing town")
                records.append(item)
            break
    if not records:
        raise ValueError("EPRA table not recognised. Previous data retained; review source HTML.")
    latest=max(item["valid_from"] for item in records)
    records=[item for item in records if item["valid_from"]==latest]
    if len({r["valid_to"] for r in records})!=1:
        raise ValueError("Inconsistent validity period")
    if len({r["town"].casefold() for r in records})!=len(records):
        raise ValueError("Duplicate town rows")
    return sorted(records,key=lambda r:r["town"])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--html",type=Path,help="Parse a saved EPRA HTML file for debugging")
    parser.add_argument("--output",type=Path,default=ROOT/"site/data/fuel-prices.json")
    args=parser.parse_args()
    if args.html:
        html=args.html.read_text(encoding="utf-8")
    else:
        response=requests.get(SOURCE,timeout=45,headers={"User-Agent":"KenyaInNumbers/0.1 public-statistics updater"})
        response.raise_for_status()
        if "text/html" not in response.headers.get("Content-Type",""):
            raise ValueError("Expected HTML")
        html=response.text
    records=parse_prices(html)
    if args.output.exists():
        old=json.loads(args.output.read_text())
        if old.get("records") and max(r["valid_from"] for r in old["records"])>records[0]["valid_from"]:
            raise ValueError("Source would replace data with an older period")
        if old.get("records")==records:
            print("No data changes; keeping original successful-fetch timestamp")
            return
    payload={"schema_version":1,"status":"official","source":{"name":"EPRA","url":SOURCE},"fetched_at":datetime.now(timezone.utc).isoformat(),"records":records}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=args.output.parent,delete=False,encoding="utf-8") as file:
        json.dump(payload,file,indent=2);file.write("\n");temporary=file.name
    os.replace(temporary,args.output)
    print(f"Saved {len(records)} towns; period begins {records[0]['valid_from']}")

if __name__=="__main__":
    main()
