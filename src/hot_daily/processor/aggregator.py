"""基于 LLM 的热搜聚合与事件族聚类"""

from collections import defaultdict
from hot_daily.models import HotItem, AggregatedNews


class NewsAggregator:
    """
    将多个来源的热搜按事件聚类为"事件族"。
    
    策略：
    1. 关键词提取 + 来源交叉匹配
    2. 同一个事件在不同平台的报道归为一族
    3. 按跨平台覆盖度排序（覆盖平台越多越重要）
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    # ── 停用词 ──
    _STOP_WORDS = frozenset(
        "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 "
        "会 着 没有 看 好 自己 这 他 她 它 们 那 与 及 或 被 把 让 对 从 "
        "为 以 能 吗 啊 呢 哦 啦 吧 呀 么 怎么 什么 如何 怎样 哪个 哪些".split()
    )

    # ── 事件关键词提取 ──
    def _extract_keywords(self, item: HotItem) -> set:
        """从标题提取关键词（去掉停用词）"""
        title = item.title.strip()
        # 简单二字以上分词
        chars = set()
        i = 0
        while i < len(title):
            if title[i] in ' "（({' :
                i += 1
                continue
            if '\u4e00' <= title[i] <= '\u9fff':
                # 取两字词
                if i + 1 < len(title) and '\u4e00' <= title[i+1] <= '\u9fff':
                    chars.add(title[i:i+2])
            i += 1

        # 去停用词
        return {c for c in chars if c not in self._STOP_WORDS and len(c) >= 2}

    # ── 事件族聚类 ──
    def cluster_events(self, items: list[HotItem]) -> dict[str, list[HotItem]]:
        """
        将热搜聚类为事件族。
        
        返回 {事件族key: [HotItem, ...]} 
        事件族key取出现最频繁的标题
        """
        # 1. 提取每条的标题和关键词
        item_keys = []  # [(item, keywords_set), ...]
        for item in items:
            kw = self._extract_keywords(item)
            item_keys.append((item, kw))

        # 2. 按关键词重叠聚类
        clusters: dict[str, list[HotItem]] = {}
        cluster_keywords: dict[str, set] = {}
        cluster_titles: dict[str, str] = {}

        for item, kw in item_keys:
            if not kw:
                continue

            # 找匹配的已有簇
            best_cluster = None
            best_overlap = 0

            for cid, ckw in cluster_keywords.items():
                overlap = len(kw & ckw)
                if overlap >= 2 and overlap > best_overlap:
                    best_overlap = overlap
                    best_cluster = cid

            if best_cluster:
                clusters[best_cluster].append(item)
                cluster_keywords[best_cluster] |= kw
            else:
                # 新簇
                cid = item.title[:20]
                clusters[cid] = [item]
                cluster_keywords[cid] = kw

        # 3. 合并小簇到相似大簇（同源合并）
        merged = self._merge_small_clusters(clusters, cluster_keywords)

        return merged

    def _merge_small_clusters(
        self,
        clusters: dict[str, list[HotItem]],
        keywords: dict[str, set],
    ) -> dict[str, list[HotItem]]:
        """将小簇（1-2条）合并到关联大簇"""
        items_list = list(clusters.items())
        items_list.sort(key=lambda x: len(x[1]), reverse=True)

        result: dict[str, list[HotItem]] = {}
        used = set()

        for cid, citems in items_list:
            if cid in used:
                continue
            result[cid] = list(citems)
            result_kw = keywords.get(cid, set())
            used.add(cid)

            # 找可以合并进来的小簇
            for cid2, citems2 in items_list:
                if cid2 in used:
                    continue
                if len(citems2) > 3:  # 大簇不合并
                    continue
                overlap = len(result_kw & keywords.get(cid2, set()))
                if overlap >= 2:
                    result[cid].extend(citems2)
                    result_kw |= keywords.get(cid2, set())
                    used.add(cid2)

        return result

    # ── 事件族 → 聚合新闻 ──
    def _event_to_news(self, event_key: str, items: list[HotItem]) -> AggregatedNews | None:
        """将一个事件族转换为聚合新闻"""
        if not items:
            return None

        # 按热度排序
        items.sort(key=lambda x: (x.rank if x.rank else 999))

        sources = list(dict.fromkeys(item.source for item in items))  # 去重保序

        # 取最完整的标题
        titles = [item.title for item in items]
        # 取最长且包含最多共有词的标题
        best_title = max(titles, key=lambda t: (
            len(t),
            sum(1 for s in sources if s in t.lower())
        ))

        # 收集各平台描述的碎片，拼接成完整描述
        descriptions = []
        seen_desc = set()
        for item in items:
            desc = (item.summary or "").strip()
            if desc and desc not in seen_desc and desc != best_title:
                seen_desc.add(desc)
                descriptions.append(desc)

        # 取跨平台热度最高的值
        hot_vals = [item.hot_value for item in items if item.hot_value]
        best_hot = hot_vals[0] if hot_vals else ""

        # 生成摘要
        summary = self._build_summary(best_title, descriptions, sources)

        return AggregatedNews(
            topic=best_title,
            summary=summary,
            sources=sources,
            hot_value=best_hot,
            related_urls=[item.url for item in items if item.url],
        )

    def _build_summary(self, title: str, descriptions: list[str], sources: list[str]) -> str:
        """从标题和碎片描述构建完整摘要
        注意：摘要仅用作信息传递，真正的文案由 ScriptGenerator 的 LLM 重写。
        """
        # 只使用降级拼接，LLM留给脚本生成器去做真正的文案
        # （避免对248个事件族都调LLM）
        # 第一条描述可能是标题的重复或问题的补充，直接使用
        clean_descs = [d for d in descriptions if d != title and title not in d]
        if not clean_descs:
            return title

        # 取第一条非重复且有实质内容的描述
        best = max(clean_descs, key=len)
        result = best
        if len(result) > 200:
            result = result[:197] + "..."
        return result

    def _llm_summarize(self, title: str, descriptions: list[str], sources: list[str]) -> str:
        """用 LLM 生成摘要（含背景因果）"""
        src_str = "/".join(sources[:5])
        desc_str = "\n".join(f"- {d}" for d in descriptions[:5])

        prompt = f"""以下是从多个平台报道的同一个事件，请写一段120字以内的完整叙述：

事件：{title}
来源：{src_str}
各平台描述：
{desc_str or "(无详细描述)"}

要求：
1. 包含事件核心事实 + 背景 + 影响
2. 逻辑连贯，适合视频配音
3. 120字以内"""

        try:
            resp = self.llm.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            # LLM失败，降级
            return title

    # ── 对外接口 ──
    def aggregate(self, all_items: list[HotItem]) -> list[AggregatedNews]:
        """完整聚合流水线"""
        # 1. 聚类为事件族
        events = self.cluster_events(all_items)
        if not events:
            return []

        # 2. 每个事件族转聚合新闻
        news_list = []
        for event_key, items in events.items():
            news = self._event_to_news(event_key, items)
            if news and news.summary:
                news_list.append(news)

        # 3. 按综合热度排序（来源覆盖度 × 热度值）
        def hot_score(n: AggregatedNews) -> float:
            # 来源覆盖度（权重高）
            src_score = len(n.sources) * 10
            # 热度数值（如果有）
            hot_val = 0
            if n.hot_value:
                import re
                m = re.search(r'([\d.]+)(万|亿)', n.hot_value)
                if m:
                    num = float(m.group(1))
                    unit = m.group(2)
                    hot_val = num * (10000 if unit == '万' else 100000000)
            return src_score + hot_val

        news_list.sort(key=hot_score, reverse=True)

        return news_list
