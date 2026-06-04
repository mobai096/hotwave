"""页面截图模块 - 使用 Playwright 截取热搜页面/新闻详情"""

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger


class ScreenshotTaker:
    """
    使用 Playwright 截取网页截图。
    支持截图热搜列表页、新闻详情页等。
    """

    def __init__(self, output_dir: str = "screenshots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._browser = None

    async def _get_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright
            p = await async_playwright().start()
            self._browser = await p.chromium.launch(headless=True)
            self._playwright = p
        return self._browser

    async def screenshot_url(
        self,
        url: str,
        filename: Optional[str] = None,
        width: int = 1920,
        height: int = 1080,
        full_page: bool = False,
    ) -> Optional[str]:
        """截取指定 URL 的页面截图"""
        try:
            browser = await self._get_browser()
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # 等页面渲染
            await asyncio.sleep(2)

            if not filename:
                from urllib.parse import quote
                safe_name = quote(url, safe="")[:50]
                filename = f"{safe_name}.png"

            output_path = self.output_dir / filename
            await page.screenshot(path=str(output_path), full_page=full_page)
            await page.close()

            logger.info(f"截图成功: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"截图失败 {url}: {e}")
            return None

    async def screenshot_multiple(self, urls: list[str]) -> list[str]:
        """批量截图"""
        results = []
        for url in urls:
            path = await self.screenshot_url(url)
            if path:
                results.append(path)
        return results

    async def close(self):
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()

    def sync_screenshot(self, url: str, **kwargs) -> Optional[str]:
        """同步版截图"""
        return asyncio.run(self.screenshot_url(url, **kwargs))
