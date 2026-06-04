"""百度热搜爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class BaiduCrawler(BaseCrawler):
    """爬取百度热搜 https://top.baidu.com/board?tab=realtime"""

    source_name = "baidu"

    def fetch(self) -> list[HotItem]:
        # 百度热搜新版 API
        url = "https://top.baidu.com/api/board?tab=realtime"
        resp = self.client.get(url, headers={
            **self._default_headers(),
            "Referer": "https://top.baidu.com/",
        })
        data = resp.json()

        items = []
        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            for i, entry in enumerate(card.get("content", [])):
                word = entry.get("word", "").strip()
                if not word:
                    continue

                # 热度值处理（可能是字符串或数字）
                raw_hot = entry.get("hotScore", 0)
                hot_val = ""
                if raw_hot:
                    try:
                        num = float(raw_hot)
                        if num >= 100000000:
                            hot_val = f"{num / 100000000:.1f}亿"
                        elif num >= 10000:
                            hot_val = f"{num / 10000:.1f}万"
                        else:
                            hot_val = f"{num:.0f}"
                    except (ValueError, TypeError):
                        hot_val = str(raw_hot)

                items.append(HotItem(
                    title=word,
                    rank=entry.get("index", i + 1),
                    hot_value=hot_val,
                    url=entry.get("url", ""),
                    source="baidu",
                    summary=entry.get("desc", ""),
                ))

        return items
