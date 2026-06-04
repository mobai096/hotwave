"""热浪本体 - 把大脑、工具、记忆、项目串起来"""

from pathlib import Path
from loguru import logger

from hotwave.core.react import ReactEngine
from hotwave.core.tool import ToolRegistry
from hotwave.tools.hot_daily import register_hot_daily_tools
from hotwave.memory.memory import Memory
from hotwave.project.project import ProjectManager
from hotwave.llm import create_llm

DEFAULT_SYSTEM_PROMPT = """# 🌊 你是热浪（Hot Wave）

你是一个 AI 视频创作助手，专门帮视频创作者追热点、写脚本、找素材、做视频。

## 人格

- 你语速快、信息密集，但对创作者有耐心
- 你有自己的审美和判断，会主动给建议
- 你尊重创作者的最终决定权——"你觉得呢？"
- 你熟悉各平台调性：抖音竖版、B站横版、视频号

## 核心原则

1. 创作者说一句话，你就能跑完全流程
2. 你有自己的判断，但不替创作者做决定
3. 遇到问题先向创作者说明情况，不擅自越界
4. 视频是艺术品，你出初稿，创作者定终稿
"""


class HotWave:
    """热浪本体"""

    def __init__(self, config: dict):
        self.config = config
        self.user_name = config.get("user_name", "创作者")

        # 初始化 LLM
        llm_config = config.get("llm", {})
        self.llm = create_llm(llm_config)
        self.model = llm_config.get("model", "deepseek-chat")

        # 初始化工具
        self.tools = ToolRegistry()
        register_hot_daily_tools(self.tools, config)

        # 初始化记忆
        memory_dir = config.get("memory_dir", "memory")
        self.memory = Memory(memory_dir)

        # 初始化项目管理
        projects_dir = config.get("projects_dir", "projects")
        self.projects = ProjectManager(projects_dir)

        # 初始化 ReAct 引擎
        self.engine = ReactEngine(
            llm_client=self.llm,
            model=self.model,
            tools=self.tools,
            system_prompt=config.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
            max_rounds=config.get("max_rounds", 15),
        )

        # 对话历史
        self.history = []

        # 加载用户记忆
        user_prefs = self.memory.get_preference_summary(self.user_name)
        if user_prefs:
            logger.info(f"📝 加载用户偏好: {user_prefs}")

    def chat(self, message: str) -> str:
        """跟热浪说话"""
        # 加载记忆偏好作为上下文
        prefs = self.memory.get_preference_summary(self.user_name)

        # 如果有偏好，加到消息里让热浪知道
        context_msg = message
        if prefs:
            context_msg = f"{prefs}\n\n用户说: {message}"

        reply = self.engine.chat(
            context_msg,
            history=self.history,
            user_name=self.user_name,
        )

        # 记录到历史
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": reply})

        return reply

    def end_conversation(self):
        """对话结束，触发记忆 review"""
        self.memory.review_conversation(self.history, self.user_name)
        logger.info("💾 记忆已更新")
