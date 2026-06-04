"""素材搜索模块 - 根据事件关键词爬取免费可商用视频素材"""

import httpx
import subprocess
import os
import re
from pathlib import Path
from typing import Optional
from loguru import logger


class MediaSearcher:
    """
    根据事件关键词搜索免费可商用视频素材。
    
    数据源（按优先级）：
    1. Pexels Video API（免费，可商用）
    2. 降级：根据关键词搜图当静态背景
    """

    def __init__(self, pexels_key: Optional[str] = None, cache_dir: str = "cache/media"):
        self.pexels_key = pexels_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=30, follow_redirects=True)
        # 提取关键词时过滤掉的词
        self._stop_words = frozenset(
            "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 "
            "会 着 没有 看 好 自己 这 那 它 们 被 让 对 从 为 以 能 吗 啊 "
            "呢 哦 啦 吧 呀 么 怎么 什么 如何 怎样".split()
        )

    def search_videos(self, topic: str, count: int = 3) -> list[str]:
        """
        根据话题关键词搜索视频素材。
        返回下载到本地的视频文件路径列表。
        """
        keywords = self._extract_keywords(topic)
        if not keywords:
            keywords = [topic[:10]]

        results = []

        # 尝试 Pexels
        if self.pexels_key:
            for kw in keywords[:2]:
                videos = self._pexels_search(kw, count // len(keywords[:2]) + 1)
                for url in videos:
                    path = self._download_video(url, kw)
                    if path:
                        results.append(path)
                    if len(results) >= count:
                        return results

        # 降级：提示无素材
        if not results:
            logger.warning(f"未找到 \"{topic[:20]}\" 相关视频素材，将使用纯色背景")

        return results

    def _extract_keywords(self, text: str) -> list[str]:
        """从标题中提取搜索关键词"""
        # 去掉括号内容（通常是平台加的话题标签）
        text = re.sub(r'[（(][^)）]*[)）]', '', text)
        # 去掉引号内容
        text = re.sub(r'[""「」『』]', '', text)

        # 取2~4字词
        words = []
        i = 0
        while i < len(text):
            if '\u4e00' <= text[i] <= '\u9fff':
                for end in range(i + 2, min(i + 5, len(text) + 1)):
                    chunk = text[i:end]
                    if chunk not in self._stop_words and len(chunk) >= 2:
                        words.append(chunk)
                i += 1
            else:
                i += 1

        # 去重排序（按长度从长到短）
        seen = set()
        unique = []
        for w in sorted(words, key=len, reverse=True):
            if w not in seen:
                seen.add(w)
                unique.append(w)

        return unique[:5]

    def _pexels_search(self, keyword: str, count: int) -> list[str]:
        """搜索 Pexels 视频，返回下载 URL 列表"""
        try:
            resp = self.client.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self.pexels_key},
                params={"query": keyword, "per_page": min(count, 5), "orientation": "portrait"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            urls = []
            for video in data.get("videos", []):
                # 取最好的画质
                files = video.get("video_files", [])
                # 优先取 hd 且竖屏的
                best = None
                for f in files:
                    if f.get("quality") in ("hd", "sd") and f.get("width", 0) <= 1080:
                        if not best or f["width"] > best["width"]:
                            best = f
                if best:
                    urls.append(best["link"])
            return urls
        except Exception as e:
            logger.warning(f"Pexels 搜索失败 [{keyword}]: {e}")
            return []

    def _download_video(self, url: str, keyword: str) -> Optional[str]:
        """下载视频到本地缓存（按关键词缓存，避免重复下载）"""
        name = f"{keyword}.mp4"
        path = str(self.cache_dir / name)

        if os.path.exists(path) and os.path.getsize(path) > 1000:
            logger.info(f"缓存命中: {name}")
            return path

        try:
            resp = self.client.get(url, follow_redirects=True, timeout=30)
            if resp.status_code == 200:
                with open(path, "wb") as f:
                    f.write(resp.content)
                size_mb = os.path.getsize(path) / 1024 / 1024
                logger.info(f"下载素材: {name} ({size_mb:.1f}MB)")
                return path
        except Exception as e:
            logger.warning(f"下载失败 {keyword}: {e}")

        return None

    def close(self):
        self.client.close()
