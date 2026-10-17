import os
from pathlib import Path
from typing import List
from ..models.workspace import Workspace, WorkspaceCreate, FileNode
from ..core.config import settings

DATA_DIR = settings.DATA_DIR


class WorkspaceService:
    @staticmethod
    def create_workspace_folder(data: WorkspaceCreate) -> Workspace:
        workspace = Workspace(**data.model_dump())
        ws_path = DATA_DIR / workspace.id
        os.makedirs(ws_path, exist_ok=True)

        # Create initial folder structure inside workspace
        (ws_path / "src").mkdir(exist_ok=True)
        (ws_path / "output" / "figures").mkdir(parents=True, exist_ok=True)
        (ws_path / "output" / "tables").mkdir(parents=True, exist_ok=True)
        (ws_path / "paper").mkdir(exist_ok=True)

        return workspace

    @staticmethod
    def get_file_tree(workspace_id: str, current_path: Path = None) -> List[FileNode]:
        if current_path is None:
            current_path = DATA_DIR / workspace_id

        if not current_path.exists():
            return []

        nodes = []
        for item in os.scandir(current_path):
            # Ignore hidden files and __pycache__
            if item.name.startswith(".") or item.name == "__pycache__":
                continue

            relative_path = os.path.relpath(item.path, DATA_DIR / workspace_id)
            node = FileNode(
                name=item.name,
                path=relative_path,
                type="directory" if item.is_dir() else "file",
                size=item.stat().st_size if item.is_file() else None,
            )

            if item.is_dir():
                node.children = WorkspaceService.get_file_tree(workspace_id, Path(item.path))

            nodes.append(node)

        return nodes
