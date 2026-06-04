"""
视频合成模块 — 两步合成：先生成视频，再叠SRT字幕

核心：
- 第一步：生成无字幕视频（背景板 + 素材 + 配音）
- 第二步：用SRT字幕文件叠加字幕（FFmpeg原生支持，时间精确到毫秒）
- 字幕时间戳 = TTS逐句时长，和音频完全同步
"""

import subprocess
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from hot_daily.models import VideoScript

THEMES = {
    "gold":  {"top": "0xF0B932", "bot": "0xF0B932", "title_c": "white", "sub_c": "white"},
    "warm":  {"top": "0xCC4422", "bot": "0xCC4422", "title_c": "white", "sub_c": "white"},
    "cool":  {"top": "0x1E3A5F", "bot": "0x1E3A5F", "title_c": "white", "sub_c": "white"},
    "dark":  {"top": "0x1A1A1A", "bot": "0x1A1A1A", "title_c": "#E0E0E0", "sub_c": "white"},
}


class VideoCompositor:
    """两步合成器：视频 + SRT字幕"""

    def __init__(self, output_dir="output/videos", width=1080, height=1920, fps=24,
                 font=None, llm_client=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width, self.height, self.fps = width, height, fps

        # 跨平台字体检测
        if font is None:
            import platform
            if platform.system() == "Windows":
                self.font = "Microsoft YaHei"
            else:
                self.font = "Noto Sans CJK SC"
        else:
            self.font = font

        self.llm = llm_client
        self.top_h = int(height * 0.22)
        self.mid_h = int(height * 0.56)
        self.bot_h = int(height * 0.22)

        # 启动时检查 FFmpeg
        self._check_ffmpeg()

    def compose(self, script, tts_path, subtitle_times=None,
                media_paths=None, output_name="output.mp4", theme="gold", deco="shadow"):
        """两步合成"""
        output_path = str(self.output_dir / output_name)
        colors = THEMES.get(theme, THEMES["gold"])
        blocks = self._build_blocks(script.sections, subtitle_times)
        if not blocks:
            return None

        content_blocks = [b for b in blocks if not b["text"].startswith("📌")]
        total_dur = max(b["end"] for b in blocks) if blocks else 10
        clean_title = self._clean_title(script.title)

        # ── 第一步：生成无字幕的基础视频 ──
        base_video = str(self.output_dir / "_base.mp4")
        filters = []

        # 背景
        filters.append(
            f"color=c={colors['bot']}:s={self.width}x{self.height}:d={total_dur}:r={self.fps}[bg]"
        )
        # 上背景板
        filters.append(
            f"[bg]drawbox=x=0:y=0:w=iw:h={self.top_h}:color={colors['top']}@1:t=fill[bg_top]"
        )

        # 素材
        mat_input = None
        if media_paths:
            for mp in media_paths:
                if mp and os.path.exists(mp) and os.path.getsize(mp) > 1000:
                    mat_input = mp
                    break

        label = "bg_top"
        if mat_input:
            filters.append(f"[{label}][0:v]overlay=0:{self.top_h}:shortest=1[bg_mat]")
            label = "bg_mat"

        # 标题（贯穿全程）
        if clean_title:
            title_text = clean_title[:22].replace("'", "’").replace(":", "：")
            y_title = self.top_h // 2 - 12
            filters.append(
                f"[{label}]drawtext=text='{title_text}'"
                f":font='{self.font}':fontcolor={colors['title_c']}:fontsize=48"
                f":x=(w-text_w)/2:y={y_title}"
                f":enable='between(t,0,{total_dur})'[vout]"
            )
            label = "vout"

        filter_graph = ";".join(filters)

        cmd = ["ffmpeg", "-y"]
        if mat_input:
            cmd.extend(["-stream_loop", "-1", "-i", mat_input])
        cmd.extend(["-i", tts_path])
        audio_idx = 1 if mat_input else 0
        cmd.extend([
            "-filter_complex", filter_graph,
            "-map", f"[{label}]", "-map", f"{audio_idx}:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-shortest", base_video,
        ])

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(base_video):
            logger.error(f"基础视频失败: {r.stderr[:200]}")
            return None

        # ── 第二步：写SRT字幕文件 ──
        srt_path = str(self.output_dir / "_subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            seq = 1
            for blk in content_blocks:
                text = blk["text"].strip()
                if not text or "关注热浪引擎" in text or "每天一分钟" in text:
                    continue
                start, end = blk["start"], blk["end"]
                if end - start <= 0:
                    continue
                # 时间格式: HH:MM:SS,mmm
                def to_srt(t):
                    h = int(t // 3600)
                    m = int((t % 3600) // 60)
                    s = int(t % 60)
                    ms = int((t - int(t)) * 1000)
                    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                f.write(f"{seq}\n")
                f.write(f"{to_srt(start)} --> {to_srt(end)}\n")
                f.write(f"{text}\n\n")
                seq += 1

        logger.info(f"SRT字幕: {seq-1}条")

        # ── 第三步：在视频上烧录SRT字幕 ──
        subprocess.run([
            "ffmpeg", "-y",
            "-i", base_video,
            "-vf", f"subtitles={srt_path}:force_style='FontName={self.font},FontSize=10,PrimaryColour=&H00FFFFFF,Alignment=2,MarginV=10'",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "copy",
            output_path,
        ], capture_output=True, text=True, timeout=120)

        # 清理临时文件
        for tmp in [base_video, srt_path]:
            try: os.remove(tmp)
            except OSError: pass

        if os.path.exists(output_path):
            logger.success(f"✅ 视频生成: {output_path}")
            self.generate_thumbnail(output_path)
            return output_path

        logger.error("合成失败")
        return None

    def _build_blocks(self, sections, times):
        blocks, ti = [], 0
        for sec in sections:
            t = sec.text.strip()
            if not t:
                continue
            if t.startswith("📌"):
                continue
            if any(k in t for k in ["关注热浪引擎", "每天一分钟"]):
                prev = blocks[-1]["end"] if blocks else 0
                blocks.append({"text": t, "start": prev, "end": prev + 2.5})
                continue
            if times and ti < len(times):
                prev = blocks[-1]["end"] if blocks else 0
                blocks.append({"text": t, "start": prev, "end": prev + times[ti]})
                ti += 1
            else:
                prev = blocks[-1]["end"] if blocks else 0
                dur = max(2.0, len(t) * 0.18)
                blocks.append({"text": t, "start": prev, "end": prev + dur})
        return blocks

    def _clean_title(self, title):
        t = title.strip()
        if len(t) <= 15:
            return t
        if self.llm:
            try:
                import httpx
                resp = httpx.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {self.llm.api_key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user",
                        "content": f"压缩成12字以内短标题：{t}"}], "max_tokens": 30, "temperature": 0.1},
                    timeout=10,
                )
                if resp.status_code == 200:
                    s = resp.json()["choices"][0]["message"]["content"].strip().strip('"\'「」')
                    if s and len(s) <= 18:
                        return s
            except Exception:
                pass
        for sep in ["？", "?", "——", "，"]:
            if sep in t:
                s = t.split(sep)[0]
                if len(s) <= 18:
                    return s
        return t[:15] + "…"

    @staticmethod
    def _check_ffmpeg():
        """检查 FFmpeg 是否可用"""
        import sys
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        except Exception:
            print("""
╔══════════════════════════════════════════╗
║  ❌ 需要 FFmpeg 才能生成视频              ║
║                                          ║
║  Linux:  apt install ffmpeg              ║
║  Mac:    brew install ffmpeg             ║
║  Windows: choco install ffmpeg           ║
║          或 https://ffmpeg.org/download   ║
╚══════════════════════════════════════════╝""", file=sys.stderr)
            sys.exit(1)

    def generate_thumbnail(self, video_path, output_name="thumbnail.jpg"):
        out = str(self.output_dir / output_name)
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", out],
                       capture_output=True, timeout=30)
        return out if os.path.exists(out) else None
