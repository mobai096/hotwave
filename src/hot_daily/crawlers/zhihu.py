"""知乎热榜爬虫"""

from hot_daily.crawlers.base import BaseCrawler
from hot_daily.models import HotItem


class ZhihuCrawler(BaseCrawler):
    """爬取知乎热榜 https://www.zhihu.com/hot
    接口发现思路参考 DailyHotApi (https://github.com/imsyy/DailyHotApi)
    """

    source_name = "zhihu"

    def fetch(self) -> list[HotItem]:
        # 用 api.zhihu.com 子域名，不需要 cookie
        url = "https://api.zhihu.com/topstory/hot-lists/total"
        resp = self.client.get(
            url,
            params={"limit": 50},
            headers={
                **self._default_headers(),
                "Referer": "https://www.zhihu.com/hot",
                "Accept": "application/json, text/plain, */*",
            },
        )

        # 如果 api.zhihu.com 失败，尝试 www.zhihu.com/hot HTML 解析
        if resp.status_code != 200:
            return self._fallback_html()

        data = resp.json()
        items = []
        for i, entry in enumerate(data.get("data", [])):
            target = entry.get("target", {})
            title = target.get("title", "").strip()
            if not title:
                continue

            # 解析热度值
            detail_text = entry.get("detail_text", "")
            hot_val = self._parse_heat(detail_text)

            question_id = target.get("id", "")
            items.append(HotItem(
                title=title,
                rank=i + 1,
                hot_value=hot_val,
                url=f"https://www.zhihu.com/question/{question_id}",
                source="zhihu",
                summary=target.get("excerpt", ""),
            ))

        return items

    def _fallback_html(self) -> list[HotItem]:
        """降级方案：爬取知乎热榜 HTML 页面"""
        try:
            resp = self.client.get(
                "https://www.zhihu.com/hot",
                headers={**self._default_headers(), "Accept": "text/html"},
            )
            if resp.status_code != 200:
                return []

            from parsel import Selector
            sel = Selector(text=resp.text)
            items = []
            for i, item in enumerate(sel.css(".HotList-item")):
                title = item.css(".HotList-itemTitle ::text").get("").strip()
                if title:
                    items.append(HotItem(
                        title=title,
                        rank=i + 1,
                        hot_value=item.css(".HotList-itemMetrics ::text").get("").strip(),
                        source="zhihu",
                        summary=item.css(".HotList-itemExcerpt ::text").get("").strip(),
                    ))
            return items
        except Exception:
            return []

    @staticmethod
    def _parse_heat(text: str) -> str:
        """解析热度文本"""
        if not text:
            return ""
        import re
        # "1234 万热度" → "1234万"
        m = re.search(r"([\d.]+)\s*万", text)
        if m:
            return f"{m.group(1)}万"
        # "1234 热度" → "1234"
        m = re.search(r"([\d.]+)\s*热度", text)
        if m:
            val = float(m.group(1))
            if val >= 10000:
                return f"{val / 10000:.0f}万"
            return str(int(val))
        return text[:20]
