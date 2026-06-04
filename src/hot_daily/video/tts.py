"""文本转语音模块 - 支持逐句生成与合并"""

import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger


class TTSGenerator:
    """
    将文本转换为语音。
    
    支持两种模式：
    - 整段生成（generate）：一次生成完整音频
    - 逐句生成（generate_by_sentences）：为每句生成独立音频并返回时间戳
    """

    def __init__(self, output_dir: str = "output/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, text: str, output_name: str = "tts_output.mp3") -> Optional[str]:
        """整段生成 TTS 音频文件"""
        output_path = self.output_dir / output_name
        try:
            return self._edge_tts(text, str(output_path))
        except Exception as e:
            logger.warning(f"Edge-TTS 失败: {e}")
            try:
                return self._gtts(text, str(output_path))
            except Exception as e2:
                logger.warning(f"gTTS 降级失败: {e2}")
                return None

    def generate_by_sentences(
        self,
        sentences: list[str],
        output_name: str = "tts_output.mp3",
        lead_silence: float = 0.0,
    ) -> Optional[tuple[str, list[float]]]:
        """
        逐句生成 TTS，返回 (合并音频路径, 每句时长列表)。
        开头自动插入 lead_silence 秒静音对齐标题画面。
        
        sentences: 句子列表（按序朗读）
        lead_silence: 开头静音秒数（对齐标题画面）
        returns: (merged_audio_path, durations_in_seconds)
        """
        audio_files = []
        durations = []

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                durations.append(0.1)
                continue

            tmp_path = str(self.output_dir / f"_tmp_{i}.mp3")
            try:
                self._edge_tts(sentence, tmp_path)
            except Exception:
                try:
                    self._gtts(sentence, tmp_path)
                except Exception:
                    logger.warning(f"句子{i} TTS 失败，跳过: {sentence[:20]}")
                    durations.append(0.5)
                    continue

            # 获取实际时长
            dur = self._get_duration(tmp_path)
            durations.append(max(dur, 0.3))  # 最少0.3秒
            audio_files.append(tmp_path)

        if not audio_files:
            return None

        # 合并所有音频片段
        output_path = str(self.output_dir / output_name)
        self._merge_audios(audio_files, output_path, lead_silence)

        # 清理临时文件
        for f in audio_files:
            try:
                Path(f).unlink()
            except OSError:
                pass

        return output_path, durations

    def _edge_tts(self, text: str, output_path: str) -> str:
        """使用 Edge-TTS"""
        result = subprocess.run(
            ["edge-tts", "--version"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("edge-tts not installed")

        subprocess.run(
            [
                "edge-tts",
                "--voice", "zh-CN-YunjianNeural",
                "--text", text,
                "--write-media", output_path,
            ],
            check=True, timeout=60,
        )
        return output_path

    def _gtts(self, text: str, output_path: str) -> str:
        """使用 gTTS 降级"""
        from gtts import gTTS
        tts = gTTS(text=text, lang="zh-cn", slow=False)
        tts.save(output_path)
        return output_path

    def _merge_audios(self, audio_files: list[str], output_path: str, lead_silence: float = 2.0):
        """用 ffmpeg 拼接多个音频文件，开头可插静音对齐标题画面。"""
        inputs = []
        for af in audio_files:
            inputs.extend(["-i", af])

        n = len(audio_files)

        # aevalsrc 生成静音片段
        filter_parts = []
        if lead_silence > 0:
            # 生成静音 → 拼到正文前
            silence_dur = f"{lead_silence:.2f}"
            filter_parts.append(f"aevalsrc=0:d={silence_dur}[sil]")
            concat_inputs = "[sil]"
            concat_n = n + 1
            for i in range(n):
                concat_inputs += f"[{i}:a]"
        else:
            concat_inputs = ""
            concat_n = n
            for i in range(n):
                concat_inputs += f"[{i}:a]"

        filter_str = f"{';'.join(filter_parts)};{concat_inputs}concat=n={concat_n}:v=0:a=1[out]"
        if not filter_parts:
            filter_str = f"{concat_inputs}concat=n={concat_n}:v=0:a=1[out]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"音频合并失败: {result.stderr[:200]}")
            raise RuntimeError("音频合并失败")

    def _get_duration(self, audio_path: str) -> float:
        """获取音频时长（秒）"""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0
