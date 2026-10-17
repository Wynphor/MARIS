"""
SubmissionService — 提交包打包与合规校验

支持：
  - ZIP 打包（通用）
  - RAR 打包（需要系统安装 rar 或 7z）
  - 按竞赛类型校验必需文件
  - 20MB 硬性大小限制
  - MD5 校验和生成
"""
import os
import json
import zipfile
import hashlib
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List
from ..core.config import settings

# Per-competition required files and rules
CONTEST_PROFILES = {
    "CUMCM": {
        "name": "全国大学生数学建模竞赛",
        "max_size_mb": 20,
        "preferred_format": "rar",
        "required_dirs": {
            "paper": [".pdf"],
            "src": [".py"],
        },
        "optional_dirs": {
            "output": [".png", ".csv", ".txt", ".json"],
            "data/raw": [".csv", ".xlsx", ".xls", ".json"],
        },
        "forbidden": ["__pycache__", ".git", ".DS_Store", "Thumbs.db", ".env"],
        "notes": "国赛要求提交 PDF 论文 + 源代码 + 数据文件，推荐 RAR 压缩，≤20MB。",
    },
    "MCM_ICM": {
        "name": "美国大学生数学建模竞赛",
        "max_size_mb": 25,
        "preferred_format": "zip",
        "required_dirs": {
            "paper": [".pdf"],
            "src": [".py"],
        },
        "optional_dirs": {
            "output": [".png", ".csv"],
        },
        "forbidden": ["__pycache__", ".git", ".DS_Store"],
        "notes": "MCM/ICM 需要 Summary Sheet + 论文 PDF，≤25MB。",
    },
    "省赛": {
        "name": "省赛",
        "max_size_mb": 20,
        "preferred_format": "rar",
        "required_dirs": {
            "paper": [".pdf"],
            "src": [".py"],
        },
        "optional_dirs": {
            "output": [".png", ".csv", ".txt"],
        },
        "forbidden": ["__pycache__", ".git"],
        "notes": "省赛要求类似国赛，PDF + 代码 + 数据，≤20MB。",
    },
}


class SubmissionService:
    @staticmethod
    def generate_md5(file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def _find_rar_tool() -> str:
        """Find available RAR/7z tool on the system."""
        for tool in ["rar", "7z", "7za"]:
            if shutil.which(tool):
                return tool
        return ""

    @staticmethod
    def _validate_files(ws_path: Path, profile: dict) -> tuple:
        """Validate required files exist. Returns (errors, warnings)."""
        errors = []
        warnings = []

        for dir_name, extensions in profile["required_dirs"].items():
            dir_path = ws_path / dir_name
            if not dir_path.exists():
                errors.append(f"缺少必需目录: {dir_name}/")
                continue
            found = False
            for ext in extensions:
                if list(dir_path.rglob(f"*{ext}")):
                    found = True
                    break
            if not found:
                errors.append(f"缺少必需文件: {dir_name}/*{', '.join(extensions)}")

        # Check total size before packing
        total_size = 0
        for f in ws_path.rglob("*"):
            if f.is_file():
                parts = f.relative_to(ws_path).parts
                if any(p in profile.get("forbidden", []) for p in parts):
                    continue
                total_size += f.stat().st_size

        max_bytes = profile["max_size_mb"] * 1024 * 1024
        if total_size > max_bytes:
            warnings.append(
                f"原始文件大小 {total_size / 1024 / 1024:.1f}MB 可能超过 "
                f"{profile['max_size_mb']}MB 限制（压缩后可能更小）"
            )

        return errors, warnings

    @staticmethod
    def pack_submission(workspace_id: str, contest_type: str = "CUMCM") -> Dict:
        """
        按竞赛规则打包提交材料。

        1. 校验必需文件
        2. 选择最优压缩格式（RAR 优先）
        3. 创建压缩包 + MD5 校验文件
        4. 验证压缩后大小
        """
        ws_path = settings.DATA_DIR / workspace_id
        dist_dir = ws_path / "submission"
        os.makedirs(dist_dir, exist_ok=True)

        # Get contest profile
        profile = CONTEST_PROFILES.get(contest_type, CONTEST_PROFILES["CUMCM"])

        # Validate required files
        errors, warnings = SubmissionService._validate_files(ws_path, profile)
        if errors:
            return {"status": "error", "errors": errors, "warnings": warnings}

        # Collect files to include
        included_files = []
        files_to_pack = []

        for dir_name, extensions in {**profile["required_dirs"], **profile.get("optional_dirs", {})}.items():
            dir_path = ws_path / dir_name
            if not dir_path.exists():
                continue
            for ext in extensions:
                for f in dir_path.rglob(f"*{ext}"):
                    # Skip forbidden patterns
                    rel = f.relative_to(ws_path)
                    if any(p in profile.get("forbidden", []) for p in rel.parts):
                        continue
                    files_to_pack.append((f, str(rel)))
                    included_files.append(str(rel))

        # Try RAR first (preferred for CUMCM)
        archive_path = None
        archive_format = "zip"
        rar_tool = SubmissionService._find_rar_tool()

        if rar_tool and profile.get("preferred_format") == "rar":
            rar_name = f"Submission_{workspace_id}.rar"
            rar_path = dist_dir / rar_name

            try:
                if rar_tool == "rar":
                    cmd = ["rar", "a", "-r", "-m5", str(rar_path)]
                    for f, rel in files_to_pack:
                        cmd.append(str(f))
                    result = subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(ws_path))
                else:
                    # Use 7z
                    cmd = ["7z", "a", "-tzip", str(rar_path).replace(".rar", ".zip")]
                    for f, rel in files_to_pack:
                        cmd.append(str(f))
                    result = subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(ws_path))
                    rar_path = rar_path.with_suffix(".zip")
                    rar_name = rar_name.replace(".rar", ".zip")

                if result.returncode == 0 and rar_path.exists():
                    archive_path = rar_path
                    archive_format = "rar" if rar_path.suffix == ".rar" else "zip"
            except Exception:
                pass  # Fall through to ZIP

        # RAR 硬保障：省赛/国赛要求 RAR 时，无工具则拒绝打包
        if archive_path is None:
            if profile.get("preferred_format") == "rar" and not rar_tool:
                return {
                    "status": "error",
                    "errors": [
                        f"❌ {profile['name']} 要求 RAR 格式打包，但系统未安装 RAR 工具。",
                        "请安装以下工具之一后重试：",
                        "  - WinRAR: https://www.win-rar.com/",
                        "  - 7-Zip: https://www.7-zip.org/",
                        "安装后确保 rar 或 7z 命令在 PATH 中可用。",
                    ],
                    "warnings": warnings,
                    "contest_type": contest_type,
                }
            elif profile.get("preferred_format") == "rar":
                warnings.append(
                    f"⚠️ RAR 打包失败，降级为 ZIP。"
                    "请检查 RAR/7z 工具是否正常。"
                )
        if archive_path is None:
            zip_name = f"Submission_{workspace_id}.zip"
            zip_path = dist_dir / zip_name

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f, rel in files_to_pack:
                    zf.write(f, arcname=rel)

            archive_path = zip_path
            archive_format = "zip"

        # Generate MD5
        archive_md5 = SubmissionService.generate_md5(archive_path)
        md5_file = dist_dir / "md5.txt"
        md5_file.write_text(f"{archive_md5} *{archive_path.name}", encoding="utf-8")

        size_mb = os.path.getsize(archive_path) / (1024 * 1024)
        is_compliant = size_mb <= profile["max_size_mb"]

        if not is_compliant:
            warnings.append(
                f"压缩包大小 {size_mb:.2f}MB 超过 {profile['max_size_mb']}MB 限制！"
                "请删除不必要的文件或降低图表分辨率。"
            )

        return {
            "status": "success",
            "archive_path": str(archive_path),
            "archive_format": archive_format,
            "md5_checksum": archive_md5,
            "size_mb": round(size_mb, 2),
            "max_size_mb": profile["max_size_mb"],
            "compliant": is_compliant,
            "included_files": included_files,
            "file_count": len(included_files),
            "contest_type": contest_type,
            "contest_name": profile["name"],
            "warnings": warnings,
            "notes": profile["notes"],
        }

    @staticmethod
    def get_contest_rules(contest_type: str) -> dict:
        """Get contest-specific packaging rules."""
        return CONTEST_PROFILES.get(contest_type, CONTEST_PROFILES["CUMCM"])
