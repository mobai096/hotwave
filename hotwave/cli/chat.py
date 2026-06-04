"""热浪 TUI 聊天界面"""

import sys
from pathlib import Path
from loguru import logger

from hotwave.core.hotwave import HotWave


BANNER = """
╔═══════════════════════════════════╗
║        🌊 Hot Wave 热浪           ║
║    AI 视频创作助手                 ║
╚═══════════════════════════════════╝
"""

HELP_TEXT = """
📖 你可以这样跟热浪说:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  "今天有什么热点？"         → 爬热搜
  "帮我做个XX的视频"        → 一句话出片
  "改成科普风"              → 局部修改
  "看看上个项目"            → 查看项目历史
  "退出" / "exit" / "quit"  → 结束对话

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def chat_loop(config: dict):
    """启动 TUI 聊天"""
    print(BANNER)

    # 初始化热浪
    print("🌊 热浪加载中...")
    try:
        hotwave = HotWave(config)
    except Exception as e:
        print(f"❌ 热浪启动失败: {e}")
        sys.exit(1)

    print("✅ 热浪就绪，随时可以开始！")
    print(HELP_TEXT)

    while True:
        try:
            user_input = input("\n🎬 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n🌊 热浪: 下次见~")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "退出"):
            print("\n🌊 热浪: 下次见，好片子等着你呢 🎬")
            break

        if user_input.lower() in ("help", "帮助", "?"):
            print(HELP_TEXT)
            continue

        # 调用热浪
        print("\n🌊 热浪: ", end="", flush=True)
        try:
            reply = hotwave.chat(user_input)
            print(reply)
        except Exception as e:
            print(f"嗯…出了点状况: {e}")

    # 对话结束，触发记忆
    hotwave.end_conversation()
    print("💾 已记住你的偏好，下次更懂你")
