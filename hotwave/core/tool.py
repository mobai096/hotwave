"""工具注册表 - 热浪知道怎么用的所有工具"""

import json
from typing import Any, Callable


class Tool:
    """一个工具 = 名字 + 描述 + 参数定义 + 执行函数"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema
        self.handler = handler

    def to_prompt(self) -> str:
        """生成给 LLM 看的工具描述"""
        return (
            f"## {self.name}\n"
            f"{self.description}\n"
            f"参数: {json.dumps(self.parameters, ensure_ascii=False)}"
        )


class ToolRegistry:
    """所有工具的注册中心"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_prompt(self) -> str:
        """生成给 LLM 看的完整工具清单"""
        parts = ["\n=== 可用工具 ==="]
        for tool in self._tools.values():
            parts.append(tool.to_prompt())
        parts.append("=== 工具结束 ===\n")
        return "\n\n".join(parts)

    def parse_call(self, text: str) -> list[dict]:
        """从 LLM 回复中解析出工具调用
        
        格式: <tool=工具名 参数1="值1" 参数2=值2>
        返回: [{"name": "工具名", "args": {参数dict}}, ...]
        """
        import re
        calls = []
        pattern = r'<tool=(\w+)\s*(.*?)\s*/?>'
        for match in re.finditer(pattern, text, re.DOTALL):
            name = match.group(1)
            args_str = match.group(2).strip()
            args = {}
            if args_str:
                # 解析 key="value" 或 key=value
                arg_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|(\S+))'
                for am in re.finditer(arg_pattern, args_str):
                    key = am.group(1)
                    val = am.group(2) if am.group(2) is not None else am.group(3)
                    args[key] = val
            calls.append({"name": name, "args": args})
        return calls

    def execute(self, name: str, args: dict) -> Any:
        """执行工具调用"""
        tool = self.get(name)
        if not tool:
            return f"错误: 未知工具 '{name}'"
        try:
            return tool.handler(**args)
        except Exception as e:
            return f"工具执行出错: {e}"
