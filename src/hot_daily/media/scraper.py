"""素材爬取模块 - 从 Pexels/Unsplash 等平台获取免费图片/视频"""

import httpx
from typing import Optional
from loguru import logger


class MediaScraper:
    """
    根据关键词自动搜索合适的图片/视频素材。
    优先用 Pexels API，降级到 Unsplash。
    """

    def __init__(
        self,
        pexels_key: Optional[str] = None,
        unsplash_key: Optional[str] = None,
    ):
        self.pexels_key = pexels_key
        self.unsplash_key = unsplash_key
        self.client = httpx.Client(timeout=15, follow_redirects=True)

    def search_image(self, keyword: str, count: int = 1) -> list[str]:
        """根据关键词搜索图片，返回 URL 列表"""
        # 优先 Pexels
        if self.pexels_key:
            urls = self._pexels_search(keyword, count, "photo")
            if urls:
                return urls

        # 降级 Unsplash
        if self.unsplash_key:
            urls = self._unsplash_search(keyword, count)
            if urls:
                return urls

        # 无 API Key，尝试公共搜索或返回空
        logger.warning(f"未配置素材 API Key，{keyword} 使用占位图")
        return []

    def search_video(self, keyword: str, count: int = 1) -> list[str]:
        """搜索视频素材"""
        if self.pexels_key:
            return self._pexels_search(keyword, count, "video")
        return []

    def _pexels_search(self, keyword: str, count: int, media_type: str) -> list[str]:
        """调用 Pexels API"""
        endpoint = {
            "photo": "https://api.pexels.com/v1/search",
            "video": "https://api.pexels.com/videos/search",
        }.get(media_type)

        if not endpoint:
            return []

        resp = self.client.get(
            endpoint,
            headers={"Authorization": self.pexels_key},
            params={"query": keyword, "per_page": count, "locale": "zh-CN"},
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        if media_type == "photo":
            return [p["src"]["medium"] for p in data.get("photos", [])[:count]]
        else:
            return [v["video_files"][0]["link"] for v in data.get("videos", [])[:count]]

    def _unsplash_search(self, keyword: str, count: int) -> list[str]:
        """调用 Unsplash API"""
        resp = self.client.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {self.unsplash_key}"},
            params={"query": keyword, "per_page": count},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [p["urls"]["regular"] for p in data.get("results", [])[:count]]

    def download_image(self, url: str, path: str) -> bool:
        """下载图片到本地"""
        try:
            resp = self.client.get(url)
            if resp.status_code == 200:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception as e:
            logger.error(f"下载图片失败 {url}: {e}")
        return False

    def close(self):
        self.client.close()
