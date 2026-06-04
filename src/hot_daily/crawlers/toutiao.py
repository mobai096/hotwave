"""今日头条热搜爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class TouTiaoCrawler(BaseCrawler):
    """爬取今日头条热榜 https://www.toutiao.com/hot-event/hot-board/
    接口发现思路参考 DailyHotApi (https://github.com/imsyy/DailyHotApi)
    """

    source_name = "toutiao"

    def fetch(self) -> list[HotItem]:
        url = "https://www.toutiao.com/hot-event/hot-board/"
        resp = self.client.get(
            url,
            params={"origin": "toutiao_pc"},
            headers={
                **self._default_headers(),
                "Referer": "https://www.toutiao.com/",
            },
        )
        data = resp.json()
        items = []
        for i, entry in enumerate(data.get("data", [])):
            title = entry.get("Title", "").strip()
            if not title:
                continue

            hot_val = ""
            raw_hot = entry.get("HotValue", "")
            if raw_hot:
                try:
                    num = float(raw_hot)
                    if num >= 100000000:
                        hot_val = f"{num / 100000000:.1f}亿"
                    elif num >= 10000:
                        hot_val = f"{num / 10000:.0f}万"
                    else:
                        hot_val = f"{num:.0f}"
                except (ValueError, TypeError):
                    hot_val = str(raw_hot)

            items.append(HotItem(
                title=title,
                rank=i + 1,
                hot_value=hot_val,
                url=f"https://www.toutiao.com/trending/{entry.get('ClusterIdStr', '')}/",
                source="toutiao",
            ))

        return items
