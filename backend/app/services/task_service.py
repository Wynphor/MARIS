"""
TaskService — Pipeline 任务持久化管理

职责：
  - 创建/更新/查询 PipelineTask 记录
  - 包装 SSE 流式生成器，自动记录事件日志
  - 自动将 AI 输出落盘到 workspace 文件（通过 OutputPersistenceService）
  - 提供任务历史查询

后端兼容性：
  - 所有公开方法接受可选的 session 参数
  - 若未传入 session，内部创建新连接（向后兼容）
  - 若传入 session，直接使用（支持事务共享）
"""
from typing import AsyncGenerator, Optional, List
from datetime import datetime, timezone
from sqlmodel import Session
from ..db.database import engine
from ..db.repositories import TaskRepository
from ..models.pipeline import PipelineTask


class TaskService:

    @staticmethod
    def create_task(workspace_id: str, stage: str, mode: str = "API",
                    provider: str = "", model_name: str = "",
                    session: Session = None) -> PipelineTask:
        """创建新的 Pipeline 任务记录。"""
        task = PipelineTask(
            workspace_id=workspace_id,
            stage=stage,
            mode=mode,
            provider=provider,
            model_name=model_name,
        )
        if session is not None:
            return TaskRepository.create(session, task)
        with Session(engine) as session:
            session.expire_on_commit = False
            result = TaskRepository.create(session, task)
            session.commit()
            return result

    @staticmethod
    def update_task(task: PipelineTask, session: Session = None):
        """更新任务记录。"""
        if session is not None:
            TaskRepository.update(session, task)
            return
        with Session(engine) as session:
            session.expire_on_commit = False
            TaskRepository.update(session, task)
            session.commit()

    @staticmethod
    def get_task(task_id: str, session: Session = None) -> Optional[PipelineTask]:
        """获取单个任务。"""
        if session is not None:
            return TaskRepository.get(session, task_id)
        with Session(engine) as session:
            return TaskRepository.get(session, task_id)

    @staticmethod
    def get_workspace_tasks(workspace_id: str, limit: int = 50,
                            session: Session = None) -> List[PipelineTask]:
        """获取某 workspace 的所有任务（按时间倒序）。"""
        if session is not None:
            return TaskRepository.get_by_workspace(session, workspace_id, limit)
        with Session(engine) as session:
            return TaskRepository.get_by_workspace(session, workspace_id, limit)

    @staticmethod
    def get_stage_tasks(workspace_id: str, stage: str,
                        session: Session = None) -> List[PipelineTask]:
        """获取某 workspace 某 stage 的所有任务。"""
        if session is not None:
            return TaskRepository.get_by_stage(session, workspace_id, stage)
        with Session(engine) as session:
            return TaskRepository.get_by_stage(session, workspace_id, stage)

    @staticmethod
    def get_latest_completed(workspace_id: str, stage: str,
                             session: Session = None) -> Optional[PipelineTask]:
        """获取某 stage 最近一次成功的任务。"""
        if session is not None:
            return TaskRepository.get_latest_completed(session, workspace_id, stage)
        with Session(engine) as session:
            return TaskRepository.get_latest_completed(session, workspace_id, stage)

    @staticmethod
    def mark_workspace_stage_completed(
        workspace_id: str,
        stage: str,
        session: Session = None,
    ) -> None:
        """Record completed stage on the workspace without blocking task completion."""
        try:
            from ..models.workspace import Workspace
            from .stage_registry import mark_stage_completed

            if session is not None:
                ws = session.get(Workspace, workspace_id)
                if ws:
                    mark_stage_completed(ws, stage)
                    session.add(ws)
                return

            with Session(engine) as local_session:
                ws = local_session.get(Workspace, workspace_id)
                if ws:
                    mark_stage_completed(ws, stage)
                    local_session.add(ws)
                    local_session.commit()
        except Exception:
            pass

    @staticmethod
    async def wrap_sse_stream(
        task: PipelineTask,
        stream: AsyncGenerator[str, None],
        session: Session = None,
    ) -> AsyncGenerator[str, None]:
        """
        包装 SSE 流式生成器：
          - 透传每个 chunk 给前端
          - 同时记录到 task.sse_events
          - 自动更新 task 状态（RUNNING → COMPLETED/FAILED）
          - 提取输出摘要
        """
        task.mark_running()
        TaskService.update_task(task, session=session)

        # Yield task_id 让前端知道是哪个任务
        yield f"data: [TASK] {task.id}\n\n"

        output_buffer = ""
        has_error = False

        # System/control message prefixes to exclude from output buffer
        _SYSTEM_PREFIXES = [
            "data: [TASK]", "data: [STATS]", "data: [INFO]", "data: [DONE]",
            "data: [TASK_COMPLETE]", "data: [SAVED]", "data: [ERROR]",
            "data: [WARNING]", "data: [SUCCESS]", "data: [STEP",
            "data: [MISSING]", "data: [OUTLIER]", "data: [STD]",
            "data: [OUTPUT]", "data: [FIGURE]", "data: [RED TEAM]",
            "data: [BLUE TEAM]", "data: [ROUND", "data: [RESULT]",
            "data: [GRAPH]", "data: [SUMMARY]", "data: [STATUS]",
        ]

        try:
            async for chunk in stream:
                # 透传给前端
                yield chunk

                # 记录到 task
                task.add_sse_event(chunk.strip())

                # 收集输出内容（排除系统消息）
                if chunk.startswith("data: ") and not any(
                    chunk.startswith(prefix) for prefix in _SYSTEM_PREFIXES
                ):
                    content = chunk[6:].strip()
                    if content:
                        output_buffer += content + "\n"

                # 检测错误
                if "[ERROR]" in chunk:
                    has_error = True

        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            yield f"data: [ERROR] {error_msg}\n\n"
            # Still try to persist partial output
            task.total_chars = len(output_buffer)
            task.mark_failed(error_msg)
            TaskService.update_task(task, session=session)
            if output_buffer:
                try:
                    from .output_persistence_service import OutputPersistenceService
                    saved_path = OutputPersistenceService.save_stage_output(
                        task.workspace_id, task.stage, output_buffer
                    )
                    if saved_path:
                        yield f"data: [SAVED] Partial output saved to: {saved_path}\n\n"
                except Exception:
                    pass
            yield f"data: [TASK_COMPLETE] {task.id} (FAILED)\n\n"
            return

        # 更新最终状态
        task.total_chars = len(output_buffer)
        if has_error and not output_buffer:
            task.mark_failed("Task completed with errors and no output")
        elif has_error:
            # Partial success: has content but also errors
            task.mark_completed(output_buffer[:2000])
            task.error_message = "Completed with warnings/errors"
        else:
            task.mark_completed(output_buffer[:2000])
        TaskService.update_task(task, session=session)

        if task.status == "COMPLETED":
            TaskService.mark_workspace_stage_completed(
                task.workspace_id,
                task.stage,
                session=session,
            )

        # ── 自动落盘：将 AI 输出保存到 workspace 文件 ──
        if output_buffer:
            try:
                from .output_persistence_service import OutputPersistenceService
                saved_path = OutputPersistenceService.save_stage_output(
                    task.workspace_id, task.stage, output_buffer
                )
                if saved_path:
                    yield f"data: [SAVED] 输出已保存到: {saved_path}\n\n"
            except Exception:
                pass  # 落盘失败不阻塞主流程

        yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"
