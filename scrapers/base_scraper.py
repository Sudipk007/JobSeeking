import asyncio
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser, Page


class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.headless: bool = config.get("headless", True)
        self.delay_ms: int = config.get("delay_between_actions_ms", 1500)
        self.site_config: dict = {}
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self.page = await context.new_page()
        return self

    async def __aexit__(self, *_):
        if self.browser:
            await self.browser.close()
        await self._playwright.stop()

    async def delay(self):
        await asyncio.sleep(self.delay_ms / 1000)

    @abstractmethod
    async def scrape(self) -> list[dict]:
        """Return a list of flat dicts — one dict per row in the Excel output."""
        ...
