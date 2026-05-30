import re
from .base_scraper import BaseScraper

PHONE_RE = re.compile(
    r"\+?1?[\s\-\.]?\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}"
)


class LinkedInScraper(BaseScraper):
    """
    Phase 1 — collect listing cards (title, company, location, posted, url)
    Phase 2 — visit each detail page for recruiter name, phone, and description
    Phase 3 — filter to jobs whose description matches qualification keywords

    Note: LinkedIn recruiter phone numbers are almost never publicly visible.
    Recruiter name is more likely when the job was posted by a person vs. a company page.
    Note: LinkedIn aggressively detects automation. If results are empty, set
    headless=false and increase delay_between_actions_ms to 3000+ in config.json.
    """

    async def scrape(self) -> list[dict]:
        site_cfg  = self.config["sites"]["linkedin"]
        url       = site_cfg["url"]
        max_items = site_cfg.get("max_items", 30)
        quals     = [q.lower() for q in self.config.get("qualifications", [])]

        # ── Phase 1: listing cards ──────────────────────────────────────────
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.delay()

        for _ in range(max(1, max_items // 10)):
            await self.page.evaluate("window.scrollBy(0, 800)")
            await self.delay()

        jobs = await self.page.evaluate(
            """(maxItems) => {
                const items = [];
                const cards = document.querySelectorAll(
                    '.jobs-search__results-list li, .base-card'
                );
                for (const card of cards) {
                    if (items.length >= maxItems) break;
                    const titleEl    = card.querySelector('.base-search-card__title, h3');
                    const companyEl  = card.querySelector('.base-search-card__subtitle, h4');
                    const locationEl = card.querySelector('.job-search-card__location');
                    const dateEl     = card.querySelector('time');
                    const linkEl     = card.querySelector('a.base-card__full-link, a');
                    if (!titleEl) continue;
                    items.push({
                        title:    titleEl.textContent.trim(),
                        company:  companyEl   ? companyEl.textContent.trim()                        : '',
                        location: locationEl  ? locationEl.textContent.trim()                       : '',
                        posted:   dateEl      ? (dateEl.getAttribute('datetime') || dateEl.textContent.trim()) : '',
                        url:      linkEl      ? linkEl.href : '',
                    });
                }
                return items;
            }""",
            max_items,
        )

        # ── Phase 2: detail pages (recruiter + description) ─────────────────
        print(f"[linkedin] {len(jobs)} listings found. Visiting detail pages...")
        for i, job in enumerate(jobs, start=1):
            print(f"[linkedin] Detail page {i}/{len(jobs)}: {job['title'][:50]}")
            job["recruiter_name"]  = "Not listed"
            job["recruiter_phone"] = "Not listed"
            job["_description"]    = ""

            if not job["url"]:
                continue

            try:
                await self.page.goto(job["url"], wait_until="domcontentloaded", timeout=15000)
                await self.delay()

                detail = await self.page.evaluate(
                    """() => {
                        // Recruiter name — LinkedIn shows this in the hirer card
                        const nameSelectors = [
                            '.hirer-card__hirer-information .text-heading-medium',
                            '.message-the-recruiter .artdeco-entity-lockup__title',
                            '.job-poster .artdeco-entity-lockup__title',
                            '.jobs-poster__name',
                        ];
                        let recruiterName = '';
                        for (const sel of nameSelectors) {
                            const el = document.querySelector(sel);
                            if (el && el.textContent.trim()) {
                                recruiterName = el.textContent.trim();
                                break;
                            }
                        }
                        // Description
                        const descEl = document.querySelector(
                            '.jobs-description__content .jobs-box__html-content, .show-more-less-html__markup'
                        );
                        const description = descEl ? descEl.innerText : '';
                        const pageText = document.body.innerText;
                        return { recruiterName, description, pageText };
                    }"""
                )

                if detail.get("recruiterName"):
                    job["recruiter_name"] = detail["recruiterName"]

                phones = PHONE_RE.findall(detail.get("pageText", ""))
                if phones:
                    job["recruiter_phone"] = phones[0].strip()

                job["_description"] = detail.get("description", "")

            except Exception as e:
                print(f"[linkedin] Warning: could not load detail page — {e}")

        # ── Phase 3: qualification filter ───────────────────────────────────
        if quals:
            filtered = []
            for job in jobs:
                desc_lower = job["_description"].lower()
                if not desc_lower or any(q in desc_lower for q in quals):
                    filtered.append(job)
            print(f"[linkedin] {len(filtered)}/{len(jobs)} jobs match qualifications.")
            jobs = filtered

        for job in jobs:
            job.pop("_description", None)

        return jobs
