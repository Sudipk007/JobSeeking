import re
from .base_scraper import BaseScraper

PHONE_RE = re.compile(
    r"\+?1?[\s\-\.]?\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}"
)


class IndeedScraper(BaseScraper):
    """
    Phase 1 — collect listing cards (title, company, location, salary, url)
    Phase 2 — visit each detail page for recruiter name, phone, and description
    Phase 3 — filter to jobs whose description matches qualification keywords
    """

    async def scrape(self) -> list[dict]:
        site_cfg   = self.config["sites"]["indeed"]
        url        = site_cfg["url"]
        max_items  = site_cfg.get("max_items", 30)
        quals      = [q.lower() for q in self.config.get("qualifications", [])]

        # ── Phase 1: listing cards ──────────────────────────────────────────
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.delay()

        all_jobs: list[dict] = []

        while len(all_jobs) < max_items:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.delay()

            jobs = await self.page.evaluate(
                """() => {
                    const items = [];
                    const cards = document.querySelectorAll(
                        '[data-testid="slider_item"], .job_seen_beacon, .jobCard_mainContent'
                    );
                    for (const card of cards) {
                        const titleEl    = card.querySelector('[data-testid="jobTitle"] span, .jobTitle span, h2 span');
                        const companyEl  = card.querySelector('[data-testid="company-name"], .companyName');
                        const locationEl = card.querySelector('[data-testid="text-location"], .companyLocation');
                        const salaryEl   = card.querySelector('[data-testid="attribute_snippet_testid"], .salary-snippet-container');
                        const linkEl     = card.querySelector('a[data-jk], a.jcs-JobTitle');
                        if (!titleEl) continue;
                        const href = linkEl ? (linkEl.href || '') : '';
                        items.push({
                            title:    titleEl.textContent.trim(),
                            company:  companyEl   ? companyEl.textContent.trim()   : '',
                            location: locationEl  ? locationEl.textContent.trim()  : '',
                            salary:   salaryEl    ? salaryEl.textContent.trim()    : 'Not listed',
                            url:      href.startsWith('http') ? href : 'https://www.indeed.com' + href,
                        });
                    }
                    return items;
                }"""
            )

            existing_urls = {j["url"] for j in all_jobs}
            new_jobs = [j for j in jobs if j["url"] not in existing_urls]
            all_jobs.extend(new_jobs)

            next_btn = self.page.locator(
                '[data-testid="pagination-page-next"], a[aria-label="Next Page"]'
            )
            if await next_btn.count() == 0 or len(all_jobs) >= max_items:
                break
            await next_btn.first.click()
            await self.delay()

        all_jobs = all_jobs[:max_items]

        # ── Phase 2: detail pages (recruiter + description) ─────────────────
        print(f"[indeed] {len(all_jobs)} listings found. Visiting detail pages...")
        for i, job in enumerate(all_jobs, start=1):
            print(f"[indeed] Detail page {i}/{len(all_jobs)}: {job['title'][:50]}")
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
                        // Recruiter name — try multiple selectors Indeed has used
                        const nameSelectors = [
                            '[data-testid="jobsearch-ContactCard-name"]',
                            '.icl-u-textBold',
                            '.hiring-insight .heading6',
                        ];
                        let recruiterName = '';
                        for (const sel of nameSelectors) {
                            const el = document.querySelector(sel);
                            if (el && el.textContent.trim()) {
                                recruiterName = el.textContent.trim();
                                break;
                            }
                        }
                        // Description text for qualification filtering
                        const descEl = document.querySelector(
                            '#jobDescriptionText, .jobsearch-jobDescriptionText'
                        );
                        const description = descEl ? descEl.innerText : '';
                        // Full visible page text for phone regex
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
                print(f"[indeed] Warning: could not load detail page — {e}")

        # ── Phase 3: qualification filter ───────────────────────────────────
        if quals:
            filtered = []
            for job in all_jobs:
                desc_lower = job["_description"].lower()
                # Keep if description is empty (couldn't load) OR matches a qualification
                if not desc_lower or any(q in desc_lower for q in quals):
                    filtered.append(job)
            print(f"[indeed] {len(filtered)}/{len(all_jobs)} jobs match qualifications.")
            all_jobs = filtered

        # Remove internal description field before returning
        for job in all_jobs:
            job.pop("_description", None)

        return all_jobs
