#!/usr/bin/env python3
"""热浪桥接 - 让小白能从 OpenClaw 调用热浪"""

import sys, os, json, yaml
from pathlib import Path

HOTWAVE_DIR = Path(__file__).parent
sys.path.insert(0, str(HOTWAVE_DIR / "src"))


def chat_with_history(message: str) -> str:
    """发消息给热浪（加载历史），返回回复"""
    from hotwave.core.hotwave import HotWave

    config_path = HOTWAVE_DIR / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    
    hw = HotWave(config)
    
    # 恢复历史
    history_file = HOTWAVE_DIR / "cache" / "chat_history.json"
    if history_file.exists():
        hw.history = json.loads(history_file.read_text(encoding="utf-8"))

    reply = hw.chat(message)

    # 存历史
    (HOTWAVE_DIR / "cache").mkdir(exist_ok=True)
    history_file.write_text(json.dumps(hw.history, ensure_ascii=False, indent=2), encoding="utf-8")

    return reply


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "chat"

    if action == "chat":
        msg = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        if msg:
            reply = chat_with_history(msg)
            print(reply)
        else:
            print("请输入消息")
    elif action == "check":
        try:
            hw = __import__("hotwave.core.hotwave", fromlist=["HotWave"]).HotWave(
                yaml.safe_load((HOTWAVE_DIR / "config.yaml").read_text())
            )
            tools = list(hw.tools._tools.keys())
            print(f"✅ 热浪就绪 | 工具: {len(tools)}个 | 用户: {hw.user_name}")
        except Exception as e:
            print(f"❌ 热浪异常: {e}")
    else:
        print(f"未知操作: {action}")
