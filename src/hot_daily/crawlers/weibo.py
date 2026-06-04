"""微博热搜爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class WeiboCrawler(BaseCrawler):
    """爬取微博热搜榜 https://weibo.com/ajax/side/hotSearch"""

    source_name = "weibo"

    def fetch(self) -> list[HotItem]:
        # 先访问首页获取 session cookie
        self.client.get("https://weibo.com/")

        # 请求热搜 API
        resp = self.client.get(
            "https://weibo.com/ajax/side/hotSearch",
            headers={"Referer": "https://weibo.com/"},
        )
        data = resp.json()

        items = []
        realtime = data.get("data", {}).get("realtime", [])

        for entry in realtime:
            word = entry.get("word", "").strip()
            if not word:
                continue

            # 热度数值
            num = entry.get("num", 0)
            hot_val = self._format_hot(num)

            # 标注：爆/热/新/沸 等
            label = entry.get("label_name", "") or ""
            icon_desc = entry.get("icon_desc", "")
            tag = label or icon_desc
            if tag:
                hot_val = f"{tag} {hot_val}".strip()

            items.append(HotItem(
                title=word,
                rank=entry.get("realpos", len(items) + 1),
                hot_value=hot_val,
                url=f"https://s.weibo.com/weibo?q=%23{word}%23",
                source="weibo",
                summary=entry.get("note", ""),
            ))

        return items

    @staticmethod
    def _format_hot(num) -> str:
        if isinstance(num, (int, float)) and num > 0:
            if num >= 100000000:
                return f"{num / 100000000:.1f}亿"
            elif num >= 10000:
                return f"{num / 10000:.0f}万"
            else:
                return str(int(num))
        return ""
