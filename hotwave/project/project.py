"""热浪的项目管理系统 - 版本控制 + 局部修改"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


class ProjectManager:
    """管理视频创作项目
    
    每个项目 = projects/{id}/
        meta.json        — 选题、风格、来源、创建时间
        v1/              — 第一版
            script.md        — 完整脚本
            tts.mp3          — 配音
            assets.json      — 素材清单（引用）
            params.json      — 合成参数
            output.mp4       — 成品视频
        v2/              — 修改版（只改有变化的部分）
        feedback.md      — 用户反馈记录
    """

    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, topic: str, style: str = "科普") -> str:
        """创建新项目，返回 project_id"""
        project_id = f"p{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = self.projects_dir / project_id
        project_dir.mkdir(parents=True)

        meta = {
            "id": project_id,
            "topic": topic,
            "style": style,
            "created_at": datetime.now().isoformat(),
            "current_version": 1,
            "status": "draft",
        }

        (project_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 创建 v1 目录
        (project_dir / "v1").mkdir()
        (project_dir / "feedback.md").write_text("", encoding="utf-8")

        return project_id

    def get_project(self, project_id: str) -> Optional[dict]:
        """读取项目元信息"""
        path = self.projects_dir / project_id / "meta.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def new_version(self, project_id: str) -> int:
        """创建新版本，返回版本号"""
        meta = self.get_project(project_id)
        if not meta:
            return -1

        new_ver = meta["current_version"] + 1
        ver_dir = self.projects_dir / project_id / f"v{new_ver}"
        ver_dir.mkdir()

        # 复制上一版的内容作为基底
        prev_dir = self.projects_dir / project_id / f"v{meta['current_version']}"
        if prev_dir.exists():
            for f in prev_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, ver_dir / f.name)

        meta["current_version"] = new_ver
        meta_path = self.projects_dir / project_id / "meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return new_ver

    def save_asset(self, project_id: str, version: int, key: str, content: str):
        """保存项目的某个资产（脚本/TTS/参数等）"""
        ver_dir = self.projects_dir / project_id / f"v{version}"
        if not ver_dir.exists():
            return False

        path = ver_dir / key
        path.write_text(content, encoding="utf-8")
        return True

    def list_projects(self) -> list[dict]:
        """列出所有项目"""
        projects = []
        for d in self.projects_dir.iterdir():
            if d.is_dir():
                meta = self.get_project(d.name)
                if meta:
                    projects.append(meta)
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)
