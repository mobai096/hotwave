"""热浪的大脑 - ReAct 循环"""

import json
import re
from pathlib import Path
from loguru import logger

from hotwave.core.tool import ToolRegistry


class ReactEngine:
    """ReAct 循环引擎
    
    流程:
        收到消息 → 让 LLM 思考(Thought) → LLM 决定调用工具(Action)
        → 执行工具得到结果(Observation) → 喂回 LLM → 循环直到 LLM 给出最终回复
    """

    def __init__(
        self,
        llm_client,
        model: str = "deepseek-chat",
        tools: ToolRegistry | None = None,
        system_prompt: str = "",
        max_rounds: int = 10,
    ):
        self.llm = llm_client
        self.model = model
        self.tools = tools or ToolRegistry()
        self.system_prompt = system_prompt
        self.max_rounds = max_rounds

    def _build_system(self, user_name: str = "用户") -> str:
        """构建系统提示词"""
        return (
            self.system_prompt
            + "\n\n"
            + "## 工作方式\n"
            "你是一个有工具使用能力的 AI 助手。你需要思考后决定做什么。\n\n"
            "回复格式:\n"
            "- 自然语言思考过程（用户看得到）\n"
            "- 如果需要调用工具: <tool=工具名 参数1=值1 参数2=\"值2\">\n"
            "- 工具结果会用 <result=...> 返回给你\n"
            "- 如果你认为任务已完成，直接回复用户即可\n"
            + self.tools.to_prompt()
        )

    def _extract_result(self, text: str) -> str | None:
        """提取工具执行结果"""
        m = re.search(r'<result=(.*?)>', text, re.DOTALL)
        return m.group(1) if m else None

    def _remove_tool_tags(self, text: str) -> str:
        """去掉 <tool=...> 标签，保留自然语言"""
        return re.sub(r'<tool=.*?>', '', text).strip()

    def chat(self, message: str, history: list | None = None, user_name: str = "用户") -> str:
        """发送一条消息给热浪，返回回复"""
        
        messages = []
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        # 构建系统消息
        system_msg = {"role": "system", "content": self._build_system(user_name)}

        for round_num in range(self.max_rounds):
            logger.info(f"🧠 思考轮次 {round_num + 1}")

            # 调 LLM
            try:
                resp = self.llm.chat.completions.create(
                    model=self.model,
                    messages=[system_msg] + messages,
                    temperature=0.7,
                )
                reply = resp.choices[0].message.content
            except Exception as e:
                return f"LLM 调用失败: {e}"

            # 检查是否有工具调用
            calls = self.tools.parse_call(reply)
            
            if not calls:
                # 没有工具调用 → 最终回复
                logger.info("✅ 热浪直接回复")
                # 把这次的思考过程加入历史
                messages.append({"role": "assistant", "content": reply})
                return reply

            # 执行工具调用
            messages.append({"role": "assistant", "content": reply})
            
            for call in calls:
                name = call["name"]
                args = call["args"]
                logger.info(f"🔧 调用工具: {name}({args})")
                
                result = self.tools.execute(name, args)
                result_str = str(result) if result is not None else "无返回值"

                # 截断过长结果
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "…(截断)"

                logger.info(f"📊 结果: {result_str[:100]}…")

                # 把结果作为 observation 喂回去
                messages.append({
                    "role": "user",
                    "content": f"<result={name}>{result_str}</result>"
                })

        # 超出最大轮数
        return "我思考太久了，要不你重新说一遍？"
