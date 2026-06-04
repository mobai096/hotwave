"""热浪工具集 - 封装 hot-daily 能力为可调用的工具"""

from loguru import logger

from hotwave.core.tool import Tool, ToolRegistry


def register_hot_daily_tools(registry: ToolRegistry, config: dict | None = None):
    """把 hot-daily 的现有能力注册为热浪的工具"""
    cfg = config or {}

    # ─── 爬热搜 ───
    def search_hot_topics(platform: str = "all", count: str = "10"):
        """爬取热搜榜单"""
        from hot_daily.crawlers import (
            WeiboCrawler, ZhihuCrawler, BaiduCrawler,
            BilibiliCrawler, TouTiaoCrawler, DouyinCrawler,
        )
        crawler_map = {
            "weibo": WeiboCrawler,
            "zhihu": ZhihuCrawler,
            "baidu": BaiduCrawler,
            "bilibili": BilibiliCrawler,
            "toutiao": TouTiaoCrawler,
            "douyin": DouyinCrawler,
        }

        if platform == "all":
            crawlers = list(crawler_map.values())
        elif platform in crawler_map:
            crawlers = [crawler_map[platform]]
        else:
            return f"未知平台: {platform}，可选: {','.join(crawler_map.keys())}"

        all_items = []
        errors = []
        for CrawlerCls in crawlers:
            try:
                c = CrawlerCls()
                items = c.fetch_safe()
                all_items.extend(items)
                c.close()
            except Exception as e:
                errors.append(f"{CrawlerCls.source_name}: {e}")

        # 按 rank 排序
        all_items.sort(key=lambda x: x.rank)

        limit = min(int(count), len(all_items))
        result = []
        for item in all_items[:limit]:
            hot = f" [{item.hot_value}]" if item.hot_value else ""
            result.append(f"#{item.rank} {item.title}{hot} ({item.source})")
        
        output = "\n".join(result) if result else "没有爬到结果"
        if errors:
            output += f"\n\n⚠️ 部分平台爬取失败: {'; '.join(errors)}"
        return output

    registry.register(Tool(
        name="search_hot_topics",
        description="爬取各大平台热搜榜单，支持微博/知乎/B站/百度/头条/抖音",
        parameters={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "平台: weibo/zhihu/bilibili/baidu/toutiao/douyin/all",
                    "default": "all"
                },
                "count": {
                    "type": "string",
                    "description": "返回条数",
                    "default": "10"
                }
            }
        },
        handler=search_hot_topics,
    ))

    # ─── 写脚本 ───
    def write_script(topic: str, style: str = "科普", duration: str = "30"):
        """生成视频脚本"""
        llm_cfg = cfg.get("llm", {})
        if not llm_cfg.get("api_key"):
            return "需要先配置 LLM API Key 才能生成脚本。请运行 hotwave onboard。"

        from openai import OpenAI
        client = OpenAI(
            api_key=llm_cfg.get("api_key", ""),
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com"),
        )

        prompt = (
            f"你是一个短视频脚本写手。请为以下话题写一个{style}风格的{duration}秒视频脚本。\n\n"
            f"话题: {topic}\n"
            f"风格: {style}\n"
            f"时长: {duration}秒\n\n"
            "要求:\n"
            "1. 脚本分3-5段，每段有旁白和画面描述\n"
            "2. 开头吸引眼球，结尾有呼吁/引导关注\n"
            "3. 标注每段时长\n"
            "4. 输出格式:\n"
            "   [0:00-0:05] 旁白: xxx\n"
            "   画面: xxx\n"
        )

        try:
            resp = client.chat.completions.create(
                model=llm_cfg.get("model", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2000,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"脚本生成失败: {e}"

    registry.register(Tool(
        name="write_script",
        description="根据热点话题生成视频脚本，包含旁白分段和时长建议",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "话题标题"},
                "style": {
                    "type": "string",
                    "description": "风格: 科普/震惊/沙雕/冷静分析",
                    "default": "科普"
                },
                "duration": {
                    "type": "string",
                    "description": "目标时长(秒)",
                    "default": "30"
                }
            },
            "required": ["topic"]
        },
        handler=write_script,
    ))

    # ─── TTS 配音 ───
    def generate_tts(text: str, voice: str = "zh-CN-YunjianNeural"):
        """将文本合成为语音"""
        from hot_daily.video.tts import TTSGenerator
        output_dir = cfg.get("tts_output_dir", "output/audio")

        try:
            tts = TTSGenerator(output_dir=output_dir)
            path = tts.generate(text, output_name="hotwave_tts.mp3")
            if path:
                return f"✅ 配音已生成: {path}"
            return "TTS 生成失败"
        except Exception as e:
            return f"TTS 出错: {e}"

    registry.register(Tool(
        name="generate_tts",
        description="将文本合成为语音，返回音频文件路径",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要朗读的文本"},
                "voice": {
                    "type": "string",
                    "description": "音色",
                    "default": "zh-CN-YunjianNeural"
                }
            },
            "required": ["text"]
        },
        handler=generate_tts,
    ))

    # ─── 搜素材 ───
    def search_media(keyword: str, count: str = "3"):
        """搜索视频素材"""
        pexels_key = cfg.get("media", {}).get("pexels_key", "")
        if not pexels_key:
            return "需要配置 Pexels API Key 才能搜索素材。可以在 config.yaml 中添加 media.pexels_key。"

        from hot_daily.media.searcher import MediaSearcher
        searcher = MediaSearcher(pexels_key=pexels_key, cache_dir="cache/media")
        try:
            paths = searcher.search_videos(keyword, count=int(count))
            if paths:
                return f"✅ 找到 {len(paths)} 个素材:\n" + "\n".join(paths)
            return "没有找到匹配的素材"
        except Exception as e:
            return f"素材搜索失败: {e}"

    registry.register(Tool(
        name="search_media",
        description="根据关键词搜索视频素材（Pexels 免费可商用）",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "count": {
                    "type": "string",
                    "description": "需要数量",
                    "default": "3"
                }
            },
            "required": ["keyword"]
        },
        handler=search_media,
    ))

    # ─── 预览素材画面 ───
    def preview_frames(video_path: str, frames: str = "3"):
        """抽帧查看视频素材画面"""
        import subprocess, json, base64
        from pathlib import Path

        vpath = Path(video_path)
        if not vpath.exists():
            return f"文件不存在: {video_path}"

        frame_dir = Path("cache/frames")
        frame_dir.mkdir(parents=True, exist_ok=True)

        # 抽帧
        n_frames = int(frames)
        try:
            # 先获取视频时长
            dur_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(vpath)],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 10
            interval = max(duration / (n_frames + 1), 0.5)

            frame_paths = []
            for i in range(n_frames):
                t = interval * (i + 1)
                out = frame_dir / f"frame_{vpath.stem}_{i}.jpg"
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(t), "-i", str(vpath),
                     "-vframes", "1", "-q:v", "2", str(out)],
                    capture_output=True, timeout=15,
                )
                if out.exists():
                    frame_paths.append(str(out))

            if not frame_paths:
                return "抽帧失败"

            result = [f"从 {video_path} 抽取了 {len(frame_paths)} 帧:"]

            # 如果有多模态 API，把帧发给 LLM 看
            llm_cfg = cfg.get("llm", {})
            vision_key = cfg.get("vision", {}).get("api_key") or llm_cfg.get("api_key")
            vision_url = cfg.get("vision", {}).get("base_url", "https://yunjuan.top/v1")
            vision_model = cfg.get("vision", {}).get("model", "qwen3-vl-flash")

            if vision_key:
                from openai import OpenAI
                vclient = OpenAI(api_key=vision_key, base_url=vision_url)
                
                for fp in frame_paths:
                    with open(fp, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    
                    try:
                        vresp = vclient.chat.completions.create(
                            model=vision_model,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "用一句话描述这个画面是什么场景、适合什么类型的视频"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                                ],
                            }],
                            max_tokens=200,
                        )
                        desc = vresp.choices[0].message.content
                        result.append(f"  🖼️ 帧{i+1}: {desc}")
                    except Exception as e:
                        result.append(f"  🖼️ 帧{i+1}: {fp} (描述失败: {e})")
            else:
                for i, fp in enumerate(frame_paths):
                    result.append(f"  🖼️ 帧{i+1}: {fp}")

            return "\n".join(result)

        except Exception as e:
            return f"预览失败: {e}"

    registry.register(Tool(
        name="preview_frames",
        description="抽帧查看视频素材的画面内容，用 AI 判断是否与文案匹配",
        parameters={
            "type": "object",
            "properties": {
                "video_path": {"type": "string", "description": "视频文件路径"},
                "frames": {
                    "type": "string",
                    "description": "抽取帧数",
                    "default": "3"
                }
            },
            "required": ["video_path"]
        },
        handler=preview_frames,
    ))

    # ─── 快速合成视频 ───
    def quick_compose(text: str, tts_path: str = "", output_name: str = "quick_video.mp4"):
        """快速合成：纯色背景 + 文字 + 配音"""
        import subprocess
        from pathlib import Path

        tts_file = Path(tts_path) if tts_path else None
        if not tts_file or not tts_file.exists():
            return f"配音文件不存在: {tts_path}"

        output_dir = Path("output/videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        output = str(output_dir / output_name)

        try:
            # 获取音频时长
            dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(tts_file)],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(dur.stdout.strip() or 10)

            # 安全处理文本
            safe_text = text.replace("'", "'").replace(":", "：").replace('"', '"')
            # 限制长度
            if len(safe_text) > 200:
                safe_text = safe_text[:200] + "…"

            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                f"color=c=0x1E3A5F:s=1080x1920:d={duration}:r=24",
                "-i", str(tts_file),
                "-filter_complex",
                f"drawtext=text='{safe_text}':font='Noto Sans CJK SC':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h*0.7:enable='between(t,0,{duration})'",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-shortest",
                output,
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            size = Path(output).stat().st_size
            return f"✅ 视频已生成: {output} ({size/1024:.0f}KB)"
        except Exception as e:
            return f"视频合成出错: {e}"

    registry.register(Tool(
        name="quick_compose",
        description="快速合成视频：把文字和配音合成为竖屏视频，纯色背景+文字+音频",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要显示的文字"},
                "tts_path": {"type": "string", "description": "配音文件路径"},
                "output_name": {
                    "type": "string",
                    "description": "输出文件名",
                    "default": "quick_video.mp4"
                }
            },
            "required": ["text", "tts_path"]
        },
        handler=quick_compose,
    ))

    # ─── 精美合成（使用 hot-daily 完整合成器） ───
    def compose_polished_video(topic: str, style: str = "科普", output_name: str = "polished.mp4"):
        """完整合成：用 hot-daily 合成器生成带字幕/特效的精美视频"""
        import subprocess, json
        from pathlib import Path
        from hot_daily.video.compositor import VideoCompositor
        from hot_daily.video.tts import TTSGenerator
        from hot_daily.models import VideoScript, ScriptSection

        output_dir = Path("output/videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_name)

        # 用 LLM 生成结构化脚本
        llm_cfg = cfg.get("llm", {})
        if not llm_cfg.get("api_key"):
            return "需要配置 LLM API Key"

        from openai import OpenAI
        client = OpenAI(
            api_key=llm_cfg.get("api_key", ""),
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com"),
        )

        prompt = (
            f"你是一个短视频脚本写手。请为话题 '{topic}' 写一个{style}风格、约30秒的脚本。\n\n"
            "输出 JSON 格式（不要其他文字）：\n"
            '{\n'
            '  "title": "视频标题",\n'
            '  "sections": [\n'
            '    {"text": "旁白文字", "duration": 5, "emotion": "neutral"},\n'
            '    {"text": "下一句旁白", "duration": 6, "emotion": "curious"}\n'
            '  ],\n'
            '  "tts_text": "完整的配音文本（所有旁白拼接在一起）"\n'
            '}\n\n'
            "要求: 总时长25-35秒，3-5个段落，开头抓眼球，结尾有引导关注"
        )

        try:
            resp = client.chat.completions.create(
                model=llm_cfg.get("model", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            script_data = json.loads(resp.choices[0].message.content)
        except Exception as e:
            return f"脚本生成失败: {e}"

        # 生成 TTS
        try:
            tts = TTSGenerator(output_dir="output/audio")
            tts_path = tts.generate(
                script_data.get("tts_text", ""),
                f"tts_{output_name.replace('.mp4','')}.mp3"
            )
            if not tts_path:
                return "TTS 生成失败"
        except Exception as e:
            return f"TTS 出错: {e}"

        # 构建 VideoScript
        sections = []
        subtitle_times = []
        for sec in script_data.get("sections", []):
            sections.append(ScriptSection(
                text=sec.get("text", ""),
                duration=float(sec.get("duration", 3)),
                emotion=sec.get("emotion", "neutral"),
            ))
            subtitle_times.append(float(sec.get("duration", 3)))

        video_script = VideoScript(
            title=script_data.get("title", topic),
            sections=sections,
            tts_text=script_data.get("tts_text", ""),
            duration_estimate=sum(subtitle_times),
        )

        # 搜素材（从话题提取关键词搜 Pexels）
        media_paths = []
        pexels_key = cfg.get("media", {}).get("pexels_key", "")
        if pexels_key:
            try:
                from hot_daily.media.searcher import MediaSearcher
                searcher = MediaSearcher(pexels_key=pexels_key, cache_dir="cache/media")
                # 用话题前几个字和风格相关词搜素材
                search_kw = topic[:15]
                media_paths = searcher.search_videos(search_kw, count=2)
                if media_paths:
                    logger.info(f"搜到 {len(media_paths)} 个素材用于合成")
            except Exception as e:
                logger.warning(f"搜素材失败（继续合成）: {e}")

        # 合成
        try:
            compositor = VideoCompositor(
                output_dir="output/videos",
                width=cfg.get("video", {}).get("width", 1080),
                height=cfg.get("video", {}).get("height", 1920),
                fps=cfg.get("video", {}).get("fps", 24),
            )

            theme_map = {"科普": "cool", "震惊": "warm", "沙雕": "gold", "冷静分析": "dark"}
            theme = theme_map.get(style, "cool")

            video_path = compositor.compose(
                script=video_script,
                tts_path=tts_path,
                subtitle_times=subtitle_times,
                media_paths=media_paths if media_paths else None,
                output_name=f"polished_{output_name}",
                theme=theme,
            )

            if video_path:
                size = Path(video_path).stat().st_size
                return f"✅ 精美视频已生成: {video_path} ({size/1024:.0f}KB)"
            return "合成失败"
        except Exception as e:
            return f"合成出错: {e}"

    registry.register(Tool(
        name="compose_polished_video",
        description="精美合成视频：用 hot-daily 完整合成器生成带字幕/背景板/主题配色的视频。需传入话题和风格",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "视频话题"},
                "style": {
                    "type": "string",
                    "description": "风格: 科普/震惊/沙雕/冷静分析",
                    "default": "科普"
                },
                "output_name": {
                    "type": "string",
                    "description": "输出文件名",
                    "default": "polished.mp4"
                }
            },
            "required": ["topic"]
        },
        handler=compose_polished_video,
    ))

    # ─── 生成配音 ───
    def text_to_speech(text: str):
        """把文字转成配音，返回音频文件路径"""
        from hot_daily.video.tts import TTSGenerator
        output_dir = cfg.get("tts_output_dir", "output/audio")

        try:
            tts = TTSGenerator(output_dir=output_dir)
            path = tts.generate(text, output_name="tts_speech.mp3")
            if path:
                return f"✅ 配音已生成: {path}"
            return "TTS 生成失败"
        except Exception as e:
            return f"TTS 出错: {e}"

    registry.register(Tool(
        name="text_to_speech",
        description="把文字转成配音音频文件",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要转语音的文字"}
            },
            "required": ["text"]
        },
        handler=text_to_speech,
    ))
