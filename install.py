#!/usr/bin/env python3
"""🌊 Hot Wave 一键安装脚本
用法: python install.py

自动检测系统环境，安装所有依赖，最后运行 onboard 配置向导。
支持 Linux / macOS / Windows。
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

VERSION = "0.1.0"
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == "windows"
IS_MACOS = SYSTEM == "darwin"
IS_LINUX = SYSTEM == "linux"


def color(text, code):
    """带颜色的终端输出"""
    if IS_WINDOWS:
        return text  # Windows 终端不一定支持 ANSI
    return f"\033[{code}m{text}\033[0m"


def green(text): return color(text, "92")
def yellow(text): return color(text, "93")
def red(text): return color(text, "91")
def blue(text): return color(text, "94")
def bold(text): return color(text, "1")


def run_cmd(cmd, check=False, timeout=120, shell=False):
    """运行命令，返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=shell
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"命令未找到: {cmd[0] if isinstance(cmd, list) else cmd}"
    except subprocess.TimeoutExpired:
        return -1, "", "超时"


def step(msg):
    """打印步骤标题"""
    print(f"\n{blue('▶')} {bold(msg)}")


def check(label, status, detail=""):
    """打印检查结果"""
    icon = green("✅") if status else red("❌")
    detail_str = f"  {detail}" if detail else ""
    print(f"  {icon} {label}{detail_str}")
    return status


# ═══════════════════════════════════════
#  检查阶段
# ═══════════════════════════════════════

def check_python():
    step("检查 Python")
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 10
    check(f"Python {v.major}.{v.minor}.{v.micro}", ok,
          "需要 >= 3.10" if not ok else "")
    return ok


def check_pip():
    step("检查 pip")
    code, out, _ = run_cmd([sys.executable, "-m", "pip", "--version"])
    ok = code == 0
    check("pip", ok)
    return ok


def check_git():
    step("检查 git")
    code, _, _ = run_cmd(["git", "--version"])
    ok = code == 0
    check("git", ok, "用于下载 Hot Wave" if not ok else "")
    return ok


def check_ffmpeg():
    step("检查 FFmpeg（视频合成需要）")
    code, out, err = run_cmd(["ffmpeg", "-version"])
    ok = code == 0
    if ok:
        ver = out.split("\n")[0] if out else ""
        check("ffmpeg", True, ver[:60])
    else:
        check("ffmpeg", False, "未安装")
    return ok


def check_playwright():
    step("检查 Playwright 浏览器（截图需要）")
    home = Path.home()
    # 检查是否有 chromium 缓存
    chrom_installed = list(home.glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"))
    if IS_WINDOWS:
        chrom_installed = list(home.glob("AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe"))
    ok = len(chrom_installed) > 0
    check("Playwright Chromium", ok, "可选，截图用" if not ok else "")
    return ok


def check_fonts():
    step("检查中文字体")
    if IS_LINUX:
        code, out, _ = run_cmd(["fc-list", ":lang=zh"])
        ok = len(out) > 0
        check("中文字体", ok, "视频字幕需要" if not ok else "")
        return ok
    elif IS_WINDOWS:
        # Windows 一般自带微软雅黑
        check("中文字体", True, "Windows 自带微软雅黑")
        return True
    elif IS_MACOS:
        check("中文字体", True, "macOS 自带苹方")
        return True
    return True


# ═══════════════════════════════════════
#  安装阶段
# ═══════════════════════════════════════

def install_python_deps():
    step("安装 Python 依赖")
    print("  运行: pip install -e .")
    code, out, err = run_cmd(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        timeout=120
    )
    if code == 0:
        check("依赖安装", True)
    else:
        check("依赖安装", False, err[:100])
    return code == 0


def install_ffmpeg():
    step("安装 FFmpeg")
    
    if IS_LINUX:
        print("  检测到 Linux，使用 apt 安装...")
        code, out, err = run_cmd(
            ["sudo", "apt", "install", "-y", "ffmpeg"],
            timeout=120
        )
        if code == 0:
            check("ffmpeg", True)
            return True
        # 没有 sudo 权限
        print("  ⚠️  需要 root 权限安装 ffmpeg:")
        print("     sudo apt install ffmpeg")
        return False
    
    elif IS_MACOS:
        print("  检测到 macOS...")
        # 检查有没有 brew
        code, _, _ = run_cmd(["brew", "--version"])
        if code == 0:
            code, _, _ = run_cmd(["brew", "install", "ffmpeg"], timeout=300)
            if code == 0:
                check("ffmpeg", True)
                return True
        print("  ⚠️ 请手动安装 ffmpeg:")
        print("     brew install ffmpeg")
        return False
    
    elif IS_WINDOWS:
        print("  ⚠️ 请手动安装 ffmpeg:")
        print("     1. 下载: https://ffmpeg.org/download.html")
        print("     2. 解压并加入 PATH")
        return False


def install_playwright():
    step("安装 Playwright Chromium")
    code, out, err = run_cmd(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        timeout=180
    )
    if code == 0:
        check("Playwright Chromium", True)
        return True
    
    # 如果 playwright install 失败（比如 Ubuntu 26.04）
    print("  ⚠️  官方安装失败，尝试手动下载...")
    # 获取 revision 号
    _, out, _ = run_cmd(
        [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
        timeout=15
    )
    import re
    m = re.search(r'chromium-(\d+)', out)
    if m:
        revision = m.group(1)
        url = f"https://playwright.azureedge.net/builds/chromium/{revision}/chromium-linux.zip"
        target = Path.home() / ".cache" / "ms-playwright" / f"chromium-{revision}"
        
        print(f"  手动下载 Chromium {revision}...")
        import urllib.request
        import zipfile
        
        try:
            zip_path = "/tmp/chromium.zip"
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(str(target))
            os.remove(zip_path)
            # symlink for headless shell
            headless_dir = target.parent / f"chromium_headless_shell-{revision}" / "chrome-linux"
            headless_dir.mkdir(parents=True, exist_ok=True)
            chrome_bin = target / "chrome-linux" / "chrome"
            if chrome_bin.exists():
                (headless_dir / "headless_shell").symlink_to(chrome_bin)
            check("Playwright Chromium", True, "手动安装")
            return True
        except Exception as e:
            print(f"  ❌ 手动下载失败: {e}")
            return False
    return False


def install_fonts():
    step("安装中文字体")
    if IS_LINUX:
        code, _, _ = run_cmd(
            ["sudo", "apt", "install", "-y", "fonts-noto-cjk", "fonts-wqy-microhei"],
            timeout=120
        )
        if code == 0:
            check("中文字体", True)
            return True
        print("  ⚠️ 可手动安装: sudo apt install fonts-noto-cjk")
        return False
    return True


# ═══════════════════════════════════════
#  主流程
# ═══════════════════════════════════════

def print_banner():
    banner = f"""
{green('╔═══════════════════════════════════════╗')}
{green('║')}       {bold('🌊 Hot Wave 一键安装')}        {green('║')}
{green('║')}      AI 视频创作助手 · v{VERSION}        {green('║')}
{green('╚═══════════════════════════════════════╝')}
"""
    print(banner)
    print(f"  系统: {platform.platform()}")
    print(f"  Python: {sys.version.split()[0]}")
    print()


def main():
    print_banner()

    checks_ok = True

    # ── 检测阶段 ──
    checks_ok &= check_python()
    checks_ok &= check_pip()
    checks_ok &= check_git()
    checks_ok &= check_ffmpeg()
    checks_ok &= check_playwright()
    checks_ok &= check_fonts()

    print(f"\n{'─' * 50}")

    # ── 安装缺失依赖 ──
    step("安装缺失依赖")
    
    _, out, _ = run_cmd(["ffmpeg", "-version"])
    if "ffmpeg" not in out:
        install_ffmpeg()
    
    home = Path.home()
    chrom_found = list(home.glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"))
    if not chrom_found:
        install_playwright()
    
    if IS_LINUX:
        _, out, _ = run_cmd(["fc-list", ":lang=zh"])
        if not out.strip():
            install_fonts()

    # ── 安装 Hot Wave ──
    step("安装 Hot Wave")
    
    # 检查当前目录是不是 hotwave 项目
    here = Path(__file__).parent
    is_project = (here / "pyproject.toml").exists()
    
    if is_project:
        print(f"  检测到项目目录: {here}")
        install_python_deps()
    else:
        print("  正在克隆仓库...")
        code, _, err = run_cmd(
            ["git", "clone", "--depth=1", "https://github.com/mobai096/hotwave.git"],
            timeout=60
        )
        if code == 0:
            os.chdir("hotwave")
            install_python_deps()
        else:
            print(f"  ❌ 克隆失败: {err}")
            sys.exit(1)

    # ── 完成 ──
    print(f"\n{'=' * 50}")
    print(green("✅ Hot Wave 安装就绪！"))
    print()
    print("  下一步：运行配置向导")
    print()
    print(f"  {bold('python install.py onboard')}")
    print(f"  {bold('hotwave onboard')}")
    print(f"  {bold('hotwave')}")
    print()
    print(f"{'=' * 50}")

    # ── 如果传了 onboard 参数，直接跑 onboard ──
    if len(sys.argv) > 1 and sys.argv[1] == "onboard":
        print("\n正在启动配置向导...\n")
        os.chdir(here)
        os.execv(sys.executable, [sys.executable, "-m", "hotwave", "onboard"])


if __name__ == "__main__":
    main()
