"""
Pipeline 模型 — PipelineRequest / PipelineStatus / PipelineTask

PipelineTask: 持久化的任务记录，存储每次 pipeline 执行的状态、日志、结果。
"""
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Column
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json
import sqlalchemy as sa


class PipelineRequest(BaseModel):
    """前端发送的 Pipeline 执行请求。"""
    workspace_id: str
    stage: str
    mode: str = "API"         # "CLI" 或 "API"
    provider: str = ""        # 留空则自动选择
    model_name: Optional[str] = None
    data_path: Optional[str] = None
    keywords: Optional[str] = None

    # UX-1: pipeline resume
    start_from: Optional[str] = Field(
        default=None,
        description="Resume run-all from this stage"
    )

    # UX-8: stage configuration parameters
    review_rounds: Optional[int] = Field(default=None, description="Number of review rounds")
    output_language: Optional[str] = Field(default=None, description="Output language: zh or en")
    run_generated_code: Optional[bool] = Field(default=None, description="Execute AI-generated code after code-gen")


class PipelineStatus(BaseModel):
    """Pipeline 执行状态（轻量级，用于列表展示）。"""
    task_id: str
    workspace_id: str
    stage: str
    status: str
    progress: float


class PipelineTask(SQLModel, table=True):
    """
    持久化的 Pipeline 任务记录。

    每次 POST /pipeline/execute 都会创建一条记录。
    任务完成后记录最终状态和输出摘要。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    workspace_id: str = Field(index=True)
    stage: str = Field(index=True)
    status: str = "PENDING"   # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    mode: str = "API"
    provider: str = ""
    model_name: str = ""

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # 结果
    output_summary: str = ""  # AI 输出的前 2000 字符
    error_message: str = ""
    sse_events: str = ""      # 序列化的 SSE 事件日志（JSON 数组）

    # 统计
    total_chars: int = 0
    duration_seconds: float = 0.0

    def add_sse_event(self, event: str):
        """追加一个 SSE 事件到日志。"""
        try:
            events = json.loads(self.sse_events) if self.sse_events else []
        except (json.JSONDecodeError, ValueError):
            events = []
        events.append(event[:500])  # 限制单条长度
        if len(events) > 200:
            events = events[-200:]
        self.sse_events = json.dumps(events, ensure_ascii=False)

    def mark_running(self):
        self.status = "RUNNING"
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, summary: str = ""):
        self.status = "COMPLETED"
        self.finished_at = datetime.now(timezone.utc)
        self.output_summary = summary[:2000]
        if self.started_at:
            self.duration_seconds = (self.finished_at - self.started_at).total_seconds()

    def mark_failed(self, error: str):
        self.status = "FAILED"
        self.finished_at = datetime.now(timezone.utc)
        self.error_message = error[:1000]
        if self.started_at:
            self.duration_seconds = (self.finished_at - self.started_at).total_seconds()

    def mark_cancelled(self):
        self.status = "CANCELLED"
        self.finished_at = datetime.now(timezone.utc)
