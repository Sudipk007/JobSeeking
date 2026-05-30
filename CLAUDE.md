# AIWORKFLOW — Job Scraper → Excel Report → Gmail

## What This Does
Automated pipeline: scrapes job listings from **Indeed** or **LinkedIn**, exports the results
to a professionally styled **3-sheet Excel workbook**, then emails it via **Gmail API (OAuth2)**.

## Stack
| Layer | Library |
|---|---|
| Browser automation | Playwright (Chromium) |
| Excel generation | openpyxl |
| Email delivery | Gmail API via `google-api-python-client` |
| Secrets management | python-dotenv (.env file) |

## File Structure
```
AIWORKFLOW/
├── .env                    ← ALL secrets (git-ignored — never commit)
├── .env.example            ← template, safe to commit
├── .gitignore              ← ignores .env, credentials.json, token.json, output/
├── CLAUDE.md               ← you are here
├── config.json             ← non-sensitive settings (URL, max_items, headless)
├── requirements.txt
├── setup_gmail.py          ← one-time OAuth2 token setup
├── main.py                 ← entry point
├── excel_generator.py      ← 3-sheet workbook with charts + dashboard
├── gmail_sender.py         ← sends report via Gmail API
└── scrapers/
    ├── __init__.py
    ├── base_scraper.py     ← shared Playwright setup (abstract)
    ├── indeed_scraper.py   ← scrapes job title, company, location, salary, URL
    └── linkedin_scraper.py ← scrapes job title, company, location, posted date, URL
```

## Secrets (.env)
```
GMAIL_RECIPIENT=you@example.com        # who receives the report
GMAIL_CREDENTIALS_FILE=credentials.json  # Google Cloud OAuth2 client secrets
GMAIL_TOKEN_FILE=token.json              # auto-generated after setup_gmail.py
```
These live **only in `.env`** — never in `config.json` or source code.

## config.json (non-sensitive only)
- `scraper` — `"indeed"` or `"linkedin"` (which site to run)
- `sites.indeed.url` / `sites.linkedin.url` — search URL with your query + location
- `sites.*.max_items` — max job listings to collect
- `headless` — `true` for silent run; `false` to watch the browser
- `delay_between_actions_ms` — slow down for bot-detection avoidance

## Excel Output (3 sheets)
| Sheet | Contents |
|---|---|
| **Dashboard** | KPI cards (total jobs, top company, top location, salary coverage), top-5 tables |
| **Jobs** | Full data table — styled headers, alternating rows, auto-filter, freeze row 1, "View Job" hyperlinks |
| **Charts** | Bar chart (top 10 companies), Bar chart (top 10 locations), Pie chart (salary coverage / recency) |

## Setup

### 1. Install
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Gmail OAuth2 (one-time)
1. [Google Cloud Console](https://console.cloud.google.com/) → create project → enable **Gmail API**
2. Credentials → Create OAuth2 Client ID (Desktop app) → download as `credentials.json`
3. Place `credentials.json` in project root
4. Run `python setup_gmail.py` → browser opens for login → generates `token.json`

### 3. Configure
Edit `config.json`:
- Set `"scraper"` to `"indeed"` or `"linkedin"`
- Update the URL to your search query + location

### 4. Run
```bash
python main.py
```

## Adding a New Scraper
1. Create `scrapers/my_site_scraper.py` extending `BaseScraper` (see `base_scraper.py`)
2. Implement `async def scrape(self) -> list[dict]` — return flat dicts
3. Add its columns to `COLUMNS` and `KEY_MAP` in `excel_generator.py`
4. Add entry under `"sites"` in `config.json`
5. Register it in `SCRAPERS` dict in `main.py`

## Common Issues
| Problem | Fix |
|---|---|
| `GMAIL_RECIPIENT is not set` | Add it to `.env` |
| `credentials.json not found` | Download from Google Cloud Console |
| `token.json invalid` | Delete it and re-run `python setup_gmail.py` |
| LinkedIn/Indeed returns empty | Set `"headless": false` and `"delay_between_actions_ms": 3000` |
| Playwright browser not found | Run `playwright install chromium` |
