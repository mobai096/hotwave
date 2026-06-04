"""核心流水线 - 逐句TTS + 精确字幕跟随"""

from pathlib import Path
from typing import Optional
from loguru import logger

from hot_daily.crawlers import (
    WeiboCrawler, ZhihuCrawler, BaiduCrawler,
    BilibiliCrawler, TouTiaoCrawler, DouyinCrawler,
)
from hot_daily.processor.aggregator import NewsAggregator
from hot_daily.processor.script_gen import ScriptGenerator
from hot_daily.video.tts import TTSGenerator
from hot_daily.video.compositor import VideoCompositor
from hot_daily.media.searcher import MediaSearcher


class Pipeline:
    """完整流水线，从爬取到视频输出"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        llm_client = self._init_llm() if self.config.get("llm", {}).get("api_key") else None

        self.aggregator = NewsAggregator(llm_client=llm_client)
        self.script_generator = ScriptGenerator(llm_client=llm_client)
        self.tts = TTSGenerator(output_dir="output/audio")
        media_cfg = self.config.get("media", {})
        self.media_searcher = MediaSearcher(
            pexels_key=media_cfg.get("pexels_key", ""),
            cache_dir="cache/media",
        )

        video_cfg = self.config.get("video", {})
        self.theme = video_cfg.get("theme", "gold")
        self.deco = video_cfg.get("deco", "shadow")
        self.compositor = VideoCompositor(
            output_dir="output/videos",
            width=video_cfg.get("width", 1080),
            height=video_cfg.get("height", 1920),
            fps=video_cfg.get("fps", 24),
            llm_client=llm_client,
        )

    def _init_llm(self):
        llm_cfg = self.config.get("llm", {})
        provider = llm_cfg.get("provider", "openai")
        api_key = llm_cfg.get("api_key", "")
        base_url = llm_cfg.get("base_url", "")
        self._model = llm_cfg.get("model", "gpt-4o-mini")
        if provider == "openai":
            from openai import OpenAI
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            return OpenAI(**kwargs)
        logger.warning(f"不支持的 LLM provider: {provider}")
        return None

    def run(self, max_videos: int = 3) -> list[str]:
        """执行完整流水线，返回视频文件路径列表"""
        logger.info("🚀 开始热浪引擎流水线")

        # 1️⃣ 爬取
        crawlers = [
            WeiboCrawler(), BaiduCrawler(), TouTiaoCrawler(),
            BilibiliCrawler(), DouyinCrawler(), ZhihuCrawler(),
        ]
        all_items = []
        for c in crawlers:
            all_items.extend(c.fetch_safe())
            c.close()
        if not all_items:
            logger.error("未爬取到任何热搜")
            return []
        logger.info(f"✅ 原始热搜共 {len(all_items)} 条")

        # 2️⃣ 聚类
        events = self.aggregator.aggregate(all_items)
        if not events:
            logger.error("未聚类到任何事件族")
            return []
        logger.info(f"✅ 事件族: {len(events)} 个")

        # 3️⃣ 逐事件生成视频
        videos = []
        for idx, event in enumerate(events[:max_videos]):
            src = "/".join(event.sources[:4])
            logger.info(f"\n{'='*40}\n🎬 #{idx+1}: {event.topic[:50]} [{src}]")

            # 生成脚本
            script = self.script_generator.generate(event)
            logger.info(f"   脚本: {len(script.sections)}段")

            # 获取正文句子（跳过标题和结尾）
            tts_sentences = []
            for sec in script.sections:
                t = sec.text.strip()
                if t.startswith("📌") or "关注 Hot Daily" in t or "每天一分钟" in t:
                    continue
                if t:
                    tts_sentences.append(t)

            if not tts_sentences:
                logger.warning("   无正文句子，跳过")
                continue

            logger.info(f"   正文: {len(tts_sentences)} 句")

            # 搜索视频素材
            media_paths = self.media_searcher.search_videos(event.topic, count=2)
            if media_paths:
                logger.info(f"   素材: {len(media_paths)} 个视频")
            else:
                logger.info("   素材: 无（使用纯色背景）")

            # 逐句 TTS
            tts_result = self.tts.generate_by_sentences(
                tts_sentences,
                output_name=f"tts_{idx}.mp3",
            )

            if not tts_result:
                logger.warning("   TTS 生成失败，尝试整段生成")
                tts_path = self.tts.generate(script.tts_text, f"tts_{idx}.mp3")
                if not tts_path:
                    continue
                subtitle_times = None
            else:
                tts_path, durations = tts_result
                # 每句时长 >= 1秒，避免字幕闪切
                subtitle_times = [max(d, 1.0) for d in durations]
                logger.info(f"   TTS: {len(durations)}句, 总时长 {sum(durations):.0f}s")
                for si, (txt, dur) in enumerate(zip(tts_sentences, durations)):
                    logger.info(f"     句{si+1}({dur:.1f}s): {txt[:40]}")

            # 合成视频
            safe = "".join(c for c in event.topic[:20] if c.isalnum()).strip() or "event"
            video_path = self.compositor.compose(
                script=script,
                tts_path=tts_path,
                subtitle_times=subtitle_times,
                media_paths=media_paths,
                output_name=f"{idx+1:02d}_{safe}.mp4",
                theme=self.theme,
                deco=self.deco,
            )

            if video_path:
                self.compositor.generate_thumbnail(video_path)
                logger.success(f"   ✅ {video_path}")
                videos.append(video_path)

        logger.info(f"\n🎉 共 {len(videos)}/{max_videos} 个视频")
        for v in videos:
            logger.info(f"  📹 {v}")
        return videos
