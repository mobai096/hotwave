"""B站热搜爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class BilibiliCrawler(BaseCrawler):
    """爬取B站热搜榜 https://www.bilibili.com/v/popular/rank/all"""

    source_name = "bilibili"

    def _default_headers(self) -> dict:
        # B站对完整UA反爬，用简单的
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
        }

    def fetch(self) -> list[HotItem]:
        url = "https://api.bilibili.com/x/web-interface/ranking/v2"
        resp = self.client.get(url, params={"rid": 0, "type": "all"})
        data = resp.json()

        items = []
        video_list = data.get("data", {}).get("list", [])
        for i, video in enumerate(video_list):
            title = video.get("title", "").strip()
            if not title:
                continue

            score = video.get("score", 0)
            hot_val = ""
            if score and isinstance(score, (int, float)) and score > 0:
                if score >= 10000:
                    hot_val = f"{score / 10000:.0f}万"
                else:
                    hot_val = f"{score:.0f}"

            items.append(HotItem(
                title=title,
                rank=i + 1,
                hot_value=hot_val,
                url=f"https://www.bilibili.com/video/{video.get('bvid', '')}",
                source="bilibili",
                summary=video.get("desc", "")[:100],
                category=video.get("tname", ""),
            ))

        return items
