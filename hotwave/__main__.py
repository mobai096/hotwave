"""热浪 CLI 入口"""

import sys
import yaml
from pathlib import Path
from loguru import logger


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置"""
    path = Path(config_path)
    if not path.exists():
        print(f"❌ 未找到配置文件 {config_path}")
        print("   请先运行: hotwave onboard")
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main():
    """CLI 主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="🌊 Hot Wave - AI 视频创作助手")
    parser.add_argument("cmd", nargs="?", default="chat",
                        help="命令: chat / onboard / help")
    parser.add_argument("--config", "-c", default="config.yaml",
                        help="配置文件路径")

    args = parser.parse_args()

    if args.cmd == "onboard":
        from hotwave.cli.onboard import onboard
        onboard()
    elif args.cmd == "help":
        parser.print_help()
    elif args.cmd == "chat":
        config = load_config(args.config)
        from hotwave.cli.chat import chat_loop
        chat_loop(config)
    else:
        print(f"未知命令: {args.cmd}")
        parser.print_help()


if __name__ == "__main__":
    main()
