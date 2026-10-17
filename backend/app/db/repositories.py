"""
Repository layer — centralized database access patterns.

Each repository is a thin, stateless wrapper around SQLModel operations.
All methods accept a `session: Session` parameter (no internal session creation).
This keeps session lifecycle management at the caller (route / service) level.
"""
from typing import Optional, List
from sqlmodel import Session, select, col
from ..models.workspace import Workspace
from ..models.pipeline import PipelineTask


class WorkspaceRepository:
    """Centralized workspace database operations."""

    @staticmethod
    def get(session: Session, workspace_id: str) -> Optional[Workspace]:
        """Fetch a workspace by primary key, or None if missing."""
        return session.get(Workspace, workspace_id)

    @staticmethod
    def exists(session: Session, workspace_id: str) -> bool:
        """Return True if a workspace with the given id exists."""
        return session.get(Workspace, workspace_id) is not None

    @staticmethod
    def update_status(session: Session, workspace_id: str, status: str) -> bool:
        """
        Update a workspace's status field.

        Returns True if the workspace was found and updated, False otherwise.
        """
        ws = session.get(Workspace, workspace_id)
        if ws is None:
            return False
        ws.status = status
        session.add(ws)
        return True

    @staticmethod
    def create(session: Session, workspace: Workspace) -> Workspace:
        """Persist a new workspace and return it (refreshed)."""
        session.add(workspace)
        session.flush()
        session.refresh(workspace)
        return workspace


class TaskRepository:
    """Centralized task (PipelineTask) database operations."""

    @staticmethod
    def create(session: Session, task: PipelineTask) -> PipelineTask:
        """Persist a new task and return it (refreshed)."""
        session.add(task)
        session.flush()
        session.refresh(task)
        return task

    @staticmethod
    def update(session: Session, task: PipelineTask) -> None:
        """Merge (upsert) a task into the session."""
        session.merge(task)

    @staticmethod
    def get(session: Session, task_id: str) -> Optional[PipelineTask]:
        """Fetch a task by primary key, or None if missing."""
        return session.get(PipelineTask, task_id)

    @staticmethod
    def get_by_workspace(
        session: Session, workspace_id: str, limit: int = 50
    ) -> List[PipelineTask]:
        """Return tasks for a workspace, newest first."""
        statement = (
            select(PipelineTask)
            .where(PipelineTask.workspace_id == workspace_id)
            .order_by(col(PipelineTask.created_at).desc())
            .limit(limit)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def get_by_stage(
        session: Session, workspace_id: str, stage: str
    ) -> List[PipelineTask]:
        """Return tasks for a specific workspace + stage, newest first."""
        statement = (
            select(PipelineTask)
            .where(PipelineTask.workspace_id == workspace_id)
            .where(PipelineTask.stage == stage)
            .order_by(col(PipelineTask.created_at).desc())
        )
        return list(session.exec(statement).all())

    @staticmethod
    def get_latest_completed(
        session: Session, workspace_id: str, stage: str
    ) -> Optional[PipelineTask]:
        """Return the most recent completed task for a workspace + stage."""
        statement = (
            select(PipelineTask)
            .where(PipelineTask.workspace_id == workspace_id)
            .where(PipelineTask.stage == stage)
            .where(PipelineTask.status == "COMPLETED")
            .order_by(col(PipelineTask.created_at).desc())
        )
        return session.exec(statement).first()
