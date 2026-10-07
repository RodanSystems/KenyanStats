# Kenya in Numbers — GitHub Pages starter

A dependency-free browser frontend with a Python EPRA importer. No database and no PHP server are required.

## Project files

- `site/index.html`: homepage, fuel selector and commute calculator.
- `site/assets/styles.css`: responsive styles.
- `site/assets/app.js`: JSON loading and calculations.
- `site/data/fuel-prices.json`: published fuel dataset.
- `scripts/update_data.py`: strict EPRA HTML-table importer.
- `tests/test_update.py`: parser failure and validity tests.
- `requirements.txt`: Python dependencies.
- `.github/workflows/update-and-deploy.yml`: daily refresh and deployment.

## What is ready

The homepage and calculator are implemented. The EPRA importer was tested against the live HTML table and downloaded 223 towns. The bundled official dataset covers 15 August–14 September 2026; at preparation time this is historical, not current. The UI marks expired data clearly. The importer selects the latest period present in the source table, which may lag behind EPRA press releases. It does not currently extract PDF releases or crawl pagination. Currency and inflation are clearly marked as pending; their importers are not implemented. No invented demo prices are included. Unknown source formats are rejected, and failed updates retain the last validated dataset.

## Run locally (Windows or Linux)

Use Python 3.12 or later. From the project root:

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\activate` on Windows, or `source .venv/bin/activate` on Linux/macOS. Then:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/update_data.py
python -m http.server 8000 --directory site
```

Visit http://localhost:8000. Keep that terminal open. Opening index.html directly through file:// will not reliably load JSON.

If the importer rejects EPRA's current table, save its HTML, inspect the headings and adapt the header matching in `parse_prices`. Test with `python scripts/update_data.py --html path/to/epra.html --output temporary-prices.json`. Do not copy prices from unofficial sites. Inspect the output against the actual publication before the first release.

## Publish on GitHub Pages

1. Create a public GitHub repository named `kenya-in-numbers`.
2. Upload the CONTENTS of this project directory to its root, including `.github/workflows/update-and-deploy.yml`. GitHub workflows must be in that exact directory. Use Git to ensure dot directories are included.
3. Make `main` the default branch (or update the workflow branch setting).
4. Under Settings → Pages → Build and deployment, choose GitHub Actions.
5. Permit workflow read/write repository access under Settings → Actions → General. The workflow commits successful data updates; branch protection may require adapting this step.
6. Under Actions, run “Update data and deploy Pages” manually. Inspect the source-fetch step for errors. A deployed page with an empty state does not prove a successful import.
7. Open the URL from the deployment job, usually https://YOUR-USERNAME.github.io/kenya-in-numbers/.

The schedule is 05:17 UTC / 08:17 Kenya time daily. Scheduled runs can be delayed; public-repository schedules can be disabled after prolonged inactivity. An unchanged dataset retains the last successful saved timestamp. If a source refresh fails, the workflow warns and deploys the existing data. A failed git push or deployment remains a failure. The starter uses major-version GitHub Action tags; pin reviewed commit SHAs if stronger supply-chain control is required.

## Before publishing statistics

Verify source reuse conditions, identify publication/reporting dates, and compare imported rows with official figures. EPRA values are maximum retail prices. This is an independent site, not affiliated with government. Never commit API secrets. Extend the same validate-before-write pattern for CBK and KNBS after verifying their current sources. Avoid public CORS proxies.
