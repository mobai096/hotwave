"""爬虫模块"""
from .base import BaseCrawler
from .weibo import WeiboCrawler
from .zhihu import ZhihuCrawler
from .baidu import BaiduCrawler
from .bilibili import BilibiliCrawler
from .toutiao import TouTiaoCrawler
from .douyin import DouyinCrawler

__all__ = [
    "BaseCrawler",
    "WeiboCrawler",
    "ZhihuCrawler",
    "BaiduCrawler",
    "BilibiliCrawler",
    "TouTiaoCrawler",
    "DouyinCrawler",
]
