from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json


class Workspace(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    question_id: str
    problem_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "INIT"  # INIT, DECOMPOSED, SOLVED, FINISHED
    completed_stages: str = "[]"  # JSON array of independently completed pipeline stages

    def get_completed_stage_set(self) -> set[str]:
        """Return completed pipeline stages, tolerating legacy/corrupt values."""
        try:
            parsed = json.loads(self.completed_stages or "[]")
        except (TypeError, json.JSONDecodeError):
            parsed = []
        return {str(stage) for stage in parsed if stage}

    def mark_stage_completed(self, stage: str):
        """Record a completed pipeline stage without losing branch-stage history."""
        stages = self.get_completed_stage_set()
        stages.add(stage)
        self.completed_stages = json.dumps(sorted(stages), ensure_ascii=False)

    def has_stage_completed(self, stage: str) -> bool:
        return stage in self.get_completed_stage_set()

class WorkspaceCreate(SQLModel):
    title: str
    question_id: str
    problem_type: str

class FileNode(SQLModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    size: Optional[int] = None
    children: Optional[List["FileNode"]] = None
