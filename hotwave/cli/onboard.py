"""热浪安装向导 - onboard CLI"""

import os
import sys
from pathlib import Path

EULA_TEXT = """
╔══════════════════════════════════════════╗
║        🌊 Hot Wave 安装向导              ║
║      AI 视频创作助手 · v0.1.0            ║
╚══════════════════════════════════════════╝

━━━━━━━━━━━ 欢迎使用 Hot Wave ━━━━━━━━━━━━━

Hot Wave 是一个 AI 视频创作助手，由大语言模型驱动。
使用前请了解以下事项：

📋 声明 & 须知

  1. Hot Wave 调用第三方 AI 模型（如 DeepSeek、Qwen-VL）
     生成内容，输出结果不代表开发者立场。

  2. 请勿使用 Hot Wave 制作违法违规内容，
     包括但不限于：虚假信息、侵权内容、色情内容。

  3. 视频素材来源于公开 API（如 Pexels），
     使用时请注意素材版权限制。

  4. 本项目为开源软件，按"现状"提供，
     不提供任何明示或暗示的担保。

  5. 你可以随时删除配置文件和数据，完全掌控自己的一切。

  6. 本工具生成的视频内容仅供学习交流，商用请自行确认版权。

────────────────────────────────────────

"""


def ask_yes_no(prompt: str, default: str = "Y") -> bool:
    """交互式 Y/n 选择"""
    suffix = f" [{'Y' if default.upper() == 'Y' else 'y'}/{'N' if default.upper() == 'N' else 'n'}]"
    while True:
        answer = input(prompt + suffix + ": ").strip().lower()
        if not answer:
            return default.upper() == "Y"
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  请输入 Y 或 N")


def ask_input(prompt: str, default: str = "", secret: bool = False) -> str:
    """交互式输入"""
    suffix = f" [{default}]" if default else ""
    if secret:
        # 简单隐蔽输入
        value = input(prompt + suffix + ": ").strip()
    else:
        value = input(prompt + suffix + ": ").strip()
    if not value and default:
        return default
    return value


def onboard():
    """运行安装向导"""
    print(EULA_TEXT)

    if not ask_yes_no("输入 Y 同意并继续，输入 N 退出", "Y"):
        print("\n❌ 已退出安装。")
        sys.exit(0)

    print("\n━━━━━━━━━━━ 开始配置 ━━━━━━━━━━━━━\n")

    config = {}

    # ─── LLM 配置 ───
    print("📡 LLM API 配置")
    print("   热浪的大脑需要一个大语言模型 API。\n")

    provider = ask_input("  选择提供商", "deepseek")
    config["llm"] = {"provider": provider}

    if provider == "deepseek":
        config["llm"]["base_url"] = "https://api.deepseek.com"
    elif provider == "openai":
        config["llm"]["base_url"] = "https://api.openai.com/v1"

    config["llm"]["api_key"] = ask_input("  API Key", secret=True)
    config["llm"]["model"] = ask_input("  模型名", "deepseek-chat")

    # ─── 用户信息 ───
    print("\n👤 用户信息")
    config["user_name"] = ask_input("  你希望热浪怎么称呼你", "创作者")

    # ─── 默认偏好 ───
    print("\n🎯 默认偏好（可后续修改）")
    config["default_style"] = ask_input("  默认视频风格", "科普")
    config["default_duration"] = ask_input("  默认视频时长(秒)", "30")

    # ─── 联动配置 ───
    print("\n🔗 联动配置")
    if ask_yes_no("  是否联动其他 AI 助手?", "N"):
        config["linked_agent"] = ask_input("  对方 agent 地址/ID")

    # ─── 保存配置 ───
    config_path = Path("config.yaml")
    import yaml
    config_path.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"\n✅ 配置已保存到 {config_path}")

    # ─── 引导页 ───
    print()
    print("╔" + "═" * 56 + "╗")
    print("║" + " " * 56 + "║")
    print("║" + "      🌊 Hot Wave 安装完成！".ljust(56) + "║")
    print("║" + "      AI 视频创作助手已就绪".ljust(56) + "║")
    print("║" + " " * 56 + "║")
    print("╠" + "═" * 56 + "╣")
    print("║" + " " * 56 + "║")
    print("║" + "  🎬  开始使用".ljust(56) + "║")
    print("║" + "      输入 hotwave 进入聊天".ljust(56) + "║")
    print("║" + "      就像跟朋友聊天一样，说一句话就能出片".ljust(56) + "║")
    print("║" + " " * 56 + "║")
    print("║" + "  📖  试试这样跟热浪说：".ljust(56) + "║")
    print("║" + "      ───────────────────────────".ljust(56) + "║")
    print("║" + "      看看今天微博有什么热点".ljust(56) + "║")
    print("║" + "      帮我把XX做个30秒科普视频".ljust(56) + "║")
    print("║" + "      换一个风格，改成震惊向".ljust(56) + "║")
    print("║" + "      帮我看看上个项目的进度".ljust(56) + "║")
    print("║" + "      ───────────────────────────".ljust(56) + "║")
    print("║" + " " * 56 + "║")
    print("║" + "  ⚙️  其他命令".ljust(56) + "║")
    print("║" + "      hotwave help    查看帮助".ljust(56) + "║")
    print("║" + "      hotwave onboard 重新配置".ljust(56) + "║")
    print("║" + "      exit / quit     退出聊天".ljust(56) + "║")
    print("║" + " " * 56 + "║")
    print("║" + "  🔗 联动".ljust(56) + "║")
    if config.get("linked_agent"):
        print("║" + f"      已关联: {config['linked_agent']}".ljust(56) + "║")
    else:
        print("║" + "      未配置（可在 config.yaml 中添加）".ljust(56) + "║")
    print("║" + " " * 56 + "║")
    print("╚" + "═" * 56 + "╝")
    print()
    print("  输入 hotwave，开始你的第一条视频创作 🌊")
