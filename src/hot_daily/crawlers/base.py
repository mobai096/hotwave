"""爬虫基类"""

import httpx
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from hot_daily.models import HotItem


class BaseCrawler(ABC):
    """所有爬虫的基类"""

    source_name: str = "base"

    def __init__(self, timeout: int = 15, proxy: Optional[str] = None):
        self.timeout = timeout
        self.proxy = proxy
        self.client = self._build_client()

    def _build_client(self) -> httpx.Client:
        kwargs = {
            "timeout": self.timeout,
            "follow_redirects": True,
            "headers": self._default_headers(),
        }
        if self.proxy:
            kwargs["proxies"] = self.proxy
        return httpx.Client(**kwargs)

    def _default_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    @abstractmethod
    def fetch(self) -> list[HotItem]:
        """爬取热搜列表，返回按热度排序的 HotItem 列表"""
        ...

    def fetch_safe(self) -> list[HotItem]:
        """安全爬取，异常时返回空列表"""
        try:
            items = self.fetch()
            logger.info(f"[{self.source_name}] 爬取成功，共 {len(items)} 条")
            return items
        except Exception as e:
            logger.error(f"[{self.source_name}] 爬取失败: {e}")
            return []

    def close(self):
        self.client.close()
