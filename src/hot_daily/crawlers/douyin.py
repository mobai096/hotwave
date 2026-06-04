"""抖音热点爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class DouyinCrawler(BaseCrawler):
    """爬取抖音热点榜 https://www.douyin.com/"""

    source_name = "douyin"

    def fetch(self) -> list[HotItem]:
        # 先访问首页获取 cookie
        self.client.get(
            "https://www.douyin.com/",
            headers={"User-Agent": self._default_headers()["User-Agent"]},
        )

        # 请求热搜 API
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        resp = self.client.get(
            url,
            headers={
                "User-Agent": self._default_headers()["User-Agent"],
                "Referer": "https://www.douyin.com/",
            },
        )
        data = resp.json().get("data", {})

        items = []
        seen = set()

        # 实时上升热点 (trending_list)
        for entry in data.get("trending_list", []):
            word = entry.get("word", "").strip()
            if word and word not in seen:
                seen.add(word)
                items.append(HotItem(
                    title=word,
                    rank=len(items) + 1,
                    hot_value=self._fmt_hot(entry.get("hot_value", 0)),
                    source="douyin",
                    category="上升热点",
                ))

        # 热搜词 (word_list)
        for entry in data.get("word_list", []):
            word = entry.get("word", "").strip()
            if word and word not in seen:
                seen.add(word)
                label = {1: "新", 2: "荐", 3: "热", 4: "爆", 5: "沸"}.get(
                    entry.get("label", 0), ""
                )
                hot_val = self._fmt_hot(entry.get("hot_value", 0))
                if label:
                    hot_val = f"{label} {hot_val}".strip()

                items.append(HotItem(
                    title=word,
                    rank=len(items) + 1,
                    hot_value=hot_val,
                    source="douyin",
                    category="热搜",
                ))

        return items

    @staticmethod
    def _fmt_hot(val) -> str:
        if isinstance(val, (int, float)) and val > 0:
            if val >= 100000000:
                return f"{val / 100000000:.1f}亿"
            elif val >= 10000:
                return f"{val / 10000:.0f}万"
            else:
                return str(int(val))
        return ""
