import os
import shutil
from pathlib import Path
from datetime import datetime
from ..core.config import settings

class SnapshotService:
    @staticmethod
    def create_snapshot(workspace_id: str, stage: str):
        """Creates a backup of the current workspace state before/after a stage."""
        ws_path = settings.DATA_DIR / workspace_id
        snapshot_dir = ws_path / ".snapshots" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stage}"
        os.makedirs(snapshot_dir, exist_ok=True)
        
        # Copy relevant directories
        for folder in ["src", "paper", "data"]:
            src_folder = ws_path / folder
            if src_folder.exists():
                shutil.copytree(src_folder, snapshot_dir / folder, dirs_exist_ok=True)
        
        return str(snapshot_dir)

    @staticmethod
    def list_snapshots(workspace_id: str):
        snapshot_root = settings.DATA_DIR / workspace_id / ".snapshots"
        if not snapshot_root.exists():
            return []
        return sorted([d.name for d in snapshot_root.iterdir() if d.is_dir()], reverse=True)

    @staticmethod
    def restore_snapshot(workspace_id: str, snapshot_name: str):
        ws_path = settings.DATA_DIR / workspace_id
        snapshot_path = ws_path / ".snapshots" / snapshot_name
        
        if not snapshot_path.exists():
            return False
            
        for folder in ["src", "paper", "data"]:
            target = ws_path / folder
            src = snapshot_path / folder
            if src.exists():
                if target.exists(): shutil.rmtree(target)
                shutil.copytree(src, target)
        return True
