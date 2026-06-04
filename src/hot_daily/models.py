"""数据模型"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class HotItem(BaseModel):
    """一条热搜"""
    title: str
    rank: int = 0
    hot_value: Optional[str] = None  # "爆" / "热" / "1000万+" 等
    url: str = ""
    source: str  # weibo / zhihu / baidu / ...
    summary: Optional[str] = None   # 摘要/描述
    category: Optional[str] = None  # 分类标签
    crawled_at: datetime = Field(default_factory=datetime.now)


class AggregatedNews(BaseModel):
    """聚合后的一条新闻"""
    topic: str                      # 主题标题
    summary: str                    # AI 提炼的核心事实（150字内）
    sources: list[str]              # 来源列表 ["微博", "知乎", ...]
    keywords: list[str] = []        # 关键词
    hot_value: str = ""             # 综合热度
    related_urls: list[str] = []    # 相关链接（含截图）
    image_urls: list[str] = []      # 配图


class VideoScript(BaseModel):
    """视频脚本"""
    title: str                      # 视频标题
    sections: list["ScriptSection"]  # 分段
    tts_text: str                   # 完整配音文本
    duration_estimate: int = 0      # 预估时长（秒）


class ScriptSection(BaseModel):
    """脚本段落"""
    text: str                       # 旁白
    image_prompt: Optional[str] = None  # 配图描述
    image_url: Optional[str] = None     # 实际配图URL
    emotion: str = "neutral"        # 语气
    duration: float = 3.0           # 建议时长（秒）
