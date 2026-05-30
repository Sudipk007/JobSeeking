import asyncio
import json
import os
import sys
from urllib.parse import urlencode

from dotenv import load_dotenv

from scrapers import IndeedScraper, LinkedInScraper
from excel_generator import generate_excel
from gmail_sender import send_email

load_dotenv()

SCRAPERS = {
    "indeed":   IndeedScraper,
    "linkedin": LinkedInScraper,
}


def load_config(path: str = "config.json") -> dict:
    with open(path) as f:
        return json.load(f)


def prompt_city() -> str:
    print("\n" + "─" * 50)
    print("  AIWORKFLOW — Job Scraper")
    print("─" * 50)
    city = input("  Enter city (e.g. New York, Chicago, Austin): ").strip()
    if not city:
        print("[error] City cannot be empty.")
        sys.exit(1)
    return city


def build_url(site_cfg: dict, city: str, scraper_name: str) -> str:
    base     = site_cfg["base_url"]
    keywords = site_cfg.get("keywords", "")
    if scraper_name == "indeed":
        return f"{base}?{urlencode({'q': keywords, 'l': city})}"
    else:
        return f"{base}?{urlencode({'keywords': keywords, 'location': city})}"


async def run_single_scraper(config: dict, scraper_name: str, city: str) -> tuple[str, list[dict]]:
    ScraperClass = SCRAPERS[scraper_name]
    site_cfg = config["sites"][scraper_name]
    site_cfg["url"] = build_url(site_cfg, city, scraper_name)
    print(f"[{scraper_name}] Starting — {site_cfg['url']}")
    async with ScraperClass(config) as scraper:
        data = await scraper.scrape()
    print(f"[{scraper_name}] Done — {len(data)} qualified jobs found.")
    return scraper_name, data


async def run(config: dict, city: str = None):
    """city is optional — if not provided, prompts in the terminal (CLI mode)."""
    scraper_setting = config.get("scraper", "indeed").lower()

    if scraper_setting not in ("indeed", "linkedin", "both"):
        print(f"[error] Invalid scraper '{scraper_setting}'. Use 'indeed', 'linkedin', or 'both'.")
        sys.exit(1)

    if city is None:
        city = prompt_city()

    print(f"\n[main] Mode         : {scraper_setting}")
    print(f"[main] City         : {city}")
    print(f"[main] Qualifications: {config.get('qualifications', [])}\n")

    if scraper_setting == "both":
        results = await asyncio.gather(
            run_single_scraper(config, "indeed",   city),
            run_single_scraper(config, "linkedin", city),
        )
        all_results = {name: data for name, data in results}
    else:
        name, data = await run_single_scraper(config, scraper_setting, city)
        all_results = {name: data}

    total = sum(len(v) for v in all_results.values())
    if total == 0:
        print("[main] No results found. Try a different city or check your connection.")
        sys.exit(1)

    print(f"\n[main] Total jobs across all sources: {total}")

    excel_path = generate_excel(all_results, scraper_setting, config)
    send_email(excel_path, config, record_count=total, city=city)

    print(f"[main] Done. Report: {excel_path}")


if __name__ == "__main__":
    cfg = load_config()
    asyncio.run(run(cfg))
