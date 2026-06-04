"""命令行入口"""

import os
import yaml
from pathlib import Path
from loguru import logger
import click

from hot_daily import __version__
from hot_daily.pipeline import Pipeline


@click.group()
@click.version_option(version=__version__)
def cli():
    """热浪引擎 - 全球热点自动浓缩流水线 🔥"""


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="配置文件路径")
@click.option("--source", "-s", multiple=True, help="指定来源（如 weibo zhihu baidu）")
@click.option("--theme", default="gold", help="视觉主题: gold/warm/cool/dark")
@click.option("--deco", default="shadow", help="文字装饰: shadow/underline/plate")
@click.option("--dry-run", is_flag=True, help="仅爬取和聚合，不生成视频")
def run(config, source, theme, deco, dry_run):
    """执行一次完整流水线"""
    # 加载配置
    cfg_path = Path(config)
    if not cfg_path.exists():
        logger.warning(f"配置文件 {config} 不存在，使用默认配置")
        cfg = {}
    else:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}

    # 过滤来源
    if source:
        cfg.setdefault("sources", {})
        for s in ["weibo", "zhihu", "baidu"]:
            cfg["sources"][s] = s in source

    # 命令行参数覆盖配置文件
    cfg.setdefault("video", {})
    cfg["video"]["theme"] = theme
    cfg["video"]["deco"] = deco

    # 创建输出目录
    for d in ["output/videos", "output/audio", "screenshots"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # 运行流水线
    pipeline = Pipeline(cfg)
    result = pipeline.run()

    if result:
        click.echo(f"\n✅ 视频已生成: {result}")
    else:
        click.echo("\n❌ 流水线执行失败")


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="配置文件路径")
def status(config):
    """查看各模块运行状态"""
    click.echo(f"热浪引擎 v{__version__}")

    # 系统信息
    import platform, sys
    click.echo(f"系统: {platform.system()} {platform.machine()}")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo("")

    click.echo("─" * 40)

    # 检查 FFmpeg
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        click.echo("✅ FFmpeg: 已安装")
    except Exception:
        click.echo("❌ FFmpeg: 未安装 (请安装: apt install ffmpeg / brew install ffmpeg)")

    # 检查 playwright
    try:
        import playwright
        click.echo("✅ Playwright: 已安装")
    except ImportError:
        click.echo("❌ Playwright: 未安装 (pip install playwright && playwright install chromium)")

    # 检查 edge-tts
    try:
        subprocess.run(["edge-tts", "--version"], capture_output=True, timeout=5)
        click.echo("✅ Edge-TTS: 已安装")
    except Exception:
        click.echo("⚠️  Edge-TTS: 未安装 (pip install edge-tts)")

    # 配置检查
    cfg_path = Path(config)
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        llm_key = cfg.get("llm", {}).get("api_key", "")
        click.echo(f"{'✅' if llm_key else '⚠️'}  LLM API: {'已配置' if llm_key else '未配置（降级运行）'}")
    else:
        click.echo("⚠️  配置文件不存在 (cp config.yaml.example config.yaml)")


@cli.command()
@click.option("--url", required=True, help="要截图的页面URL")
@click.option("--output", "-o", default=None, help="保存路径")
def screenshot(url, output):
    """手动截图指定页面"""
    from hot_daily.media.screenshot import ScreenshotTaker
    taker = ScreenshotTaker()
    path = taker.sync_screenshot(url, filename=output)
    if path:
        click.echo(f"✅ 截图保存: {path}")
    else:
        click.echo("❌ 截图失败")


@cli.command()
def web():
    """启动 Web 界面（浏览器打开）"""
    from app import main
    main()


if __name__ == "__main__":
    cli()
