"""从聚合新闻生成有态度、口语化的短视频脚本"""

from hot_daily.models import AggregatedNews, VideoScript, ScriptSection


class ScriptGenerator:
    """
    把一个热点事件聊成一段人话。
    
    核心思路：
    - 不是拼接各平台描述
    - 而是像朋友聊天一样，说说这个事怎么回事
    - 用"说白了"、"我就这么跟你说吧"来转折
    - 有观点，有态度，不是冷冰冰的事实罗列
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def generate(self, news: AggregatedNews, video_length: str = "medium") -> VideoScript:
        """
        为一个事件族生成完整视频脚本。
        video_length: short(30s) / medium(60s) / long(90s)
        """
        # 1. 生成口播文案
        article = self._chat_about(news, video_length)
        if not article:
            return self._fallback_script(news)

        # 2. 分句
        sentences = self._split_sentences(article)
        if not sentences:
            return self._fallback_script(news)

        # 3. 聊话题+短句合并 → 字幕块
        blocks = self._build_display_blocks(sentences)

        # 4. 生成脚本段
        sections = []
        total_duration = 0.0

        # 标题画面
        sections.append(ScriptSection(
            text=f"📌 {news.topic[:30]}",
            duration=2.0,
        ))
        total_duration += 2.0

        # 每个字幕块
        for block in blocks:
            text = "".join(block).strip()
            if not text:
                continue
            # 时长按完整内容算
            dur = max(2.0, len(text) * 0.18)
            sections.append(ScriptSection(text=text, duration=dur))
            total_duration += dur

        # 结尾
        sections.append(ScriptSection(
            text="关注热浪引擎，每天一分钟，补平信息差。",
            duration=2.5,
        ))
        total_duration += 2.5

        # TTS 文本（去掉特殊标记）
        tts_lines = []
        for s in sections:
            t = s.text
            if t.startswith("📌 "):
                t = t[2:]
            tts_lines.append(t)
        tts_text = "\n".join(tts_lines)

        return VideoScript(
            title=news.topic,
            sections=sections,
            tts_text=tts_text,
            duration_estimate=int(total_duration),
        )

    def _chat_about(self, news: AggregatedNews, video_length: str = "medium") -> str:
        """像朋友聊天一样说说这个事"""
        if self.llm:
            return self._llm_chat(news, video_length)

        return self._template_chat(news)

    def _llm_chat(self, news: AggregatedNews, video_length: str = "medium") -> str:
        """用 LLM 生成口语化文案"""
        src_str = "/".join(news.sources[:5])

        word_counts = {"short": "30到60字", "medium": "60到120字", "long": "120到200字"}
        wc = word_counts.get(video_length, "60到120字")

        prompt = f"""你现在是一个用大白话聊热点的朋友，不是新闻主播，也不是说书先生。

跟你聊的是这个事：

事件：{news.topic}
详细情况：{news.summary or "（暂无详情）"}
这个事在 {src_str} 等平台上了热搜。

请用一段话聊聊这事，{wc}。

要求：
- 开头多样化："哎你听说了吗"、"好家伙"、"说个事啊"、"嗐" 等等，别每次都一样
- 句中转折别固定：穿插"说白了"、"不过说真的"、"关键是"、"说到底啊"
- 可以有态度："我是服气的"、"这操作可以"、"这就离谱了"
- 节奏别太均匀，有的短有的长
- 避免AI腔调
- 一段到底，别分点"""

        try:
            # 直接用 httpx 调 DeepSeek API（避免 openai SDK 的 header 编码问题）
            import httpx
            resp = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 350,
                    "temperature": 0.9,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            return ""
        except Exception:
            return ""

    def _template_chat(self, news: AggregatedNews) -> str:
        """降级：用口语化模板包裹已有信息"""
        title = news.topic.strip() if news.topic else ""
        summary = news.summary.strip() if news.summary and news.summary != title else ""
        src_count = len(news.sources)

        if not title:
            return ""

        if summary:
            # 去掉摘要里的标题重复
            clean = summary
            if summary.startswith(title):
                clean = summary[len(title):].strip().lstrip("，。！？、；：——…")
            if not clean:
                clean = title

            # 用来源信息点缀
            src_note = f"这事在{'、'.join(news.sources[:3])}上都上了热搜。" if src_count >= 2 else ""

            templates = [
                f"说个事啊，{title}。{clean}{src_note}说白了，还是挺值得关注的。",
                f"今天来聊聊{title}。{clean}我就这么跟你说吧，这事确实有点意思。",
                f"{title}，就这么个事。{clean}{src_note}你怎么看？",
            ]
        else:
            src_note = f"这事在{'、'.join(news.sources[:3])}上都上了热搜。" if src_count >= 2 else f"这事上了{news.sources[0]}热搜。"
            templates = [
                f"说个事啊，{title}。{src_note}说白了还是值得关注的。",
                f"今天聊聊{title}。{src_note}我就这么跟你说吧，关注度不低。",
            ]

        import random
        article = random.choice(templates)
        if len(article) > 150:
            article = article[:147] + "。"
        return article

    def _split_sentences(self, text: str) -> list[str]:
        """按标点和换行分句，保证返回2段以上（至少2段）"""
        if not text:
            return []

        import re
        # 1. 先按换行切
        parts = []
        for rp in re.split(r'\n+', text):
            # 2. 再按句末标点切
            sub = re.split(r'(?<=[。！？；])\s*', rp.strip())
            for s in sub:
                s = s.strip()
                if s and len(s.strip("。！？；，、： \"'")) >= 2:
                    parts.append(s)

        # 3. 如果只有1段，强制在逗号处拆分
        if len(parts) <= 1 and text:
            parts = []
            for seg in re.split(r'(?<=[，、])\s*', text):
                seg = seg.strip()
                if seg and len(seg.strip("。！？；，、： \"'")) >= 2:
                    parts.append(seg)

        # 4. 如果还是只有1段且太长，硬切
        if len(parts) <= 1 and text and len(text) > 30:
            mid = len(text) // 2
            # 在中点附近找逗号
            pos = text.rfind("，", 0, mid)
            if pos > 0:
                parts = [text[:pos], text[pos+1:]]
            else:
                pos = text.rfind(",", 0, mid)
                if pos > 0:
                    parts = [text[:pos], text[pos+1:]]
                else:
                    # 实在找不到就在中点硬切
                    parts = [text[:mid], text[mid:]]

        return [p for p in parts if len(p.strip()) >= 2]

    def _build_display_blocks(self, sentences: list[str]) -> list[list[str]]:
        """
        生成字幕显示块。
        
        规则：
        - 默认一句一块
        - 短句（≤7字）：和下一句合并为一个块
        """
        blocks = []
        i = 0
        while i < len(sentences):
            cur = sentences[i]
            block = [cur]

            # 当前句短 → 拉下一句一起显示
            if len(cur) <= 7 and i + 1 < len(sentences):
                block.append(sentences[i + 1])
                i += 2
            else:
                i += 1

            blocks.append(block)

        return blocks

    def _fallback_script(self, news: AggregatedNews) -> VideoScript:
        """兜底"""
        return VideoScript(
            title=news.topic,
            sections=[
                ScriptSection(text=f"📌 {news.topic[:30]}", duration=2.0),
                ScriptSection(text=news.summary or news.topic, duration=5.0),
                ScriptSection(text="关注热浪引擎", duration=2.0),
            ],
            tts_text=f"{news.topic}。{news.summary or ''}。关注 Hot Daily。",
            duration_estimate=9,
        )
