"""
任务查询路由 — 查看 Pipeline 执行历史和状态
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ...services.task_service import TaskService
from ...models.pipeline import PipelineTask
import json

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    """获取单个任务详情。"""
    task = TaskService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_dict(task)


@router.get("/workspace/{workspace_id}")
async def get_workspace_tasks(workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """获取某 workspace 的所有任务历史。"""
    limit = min(limit, 200)  # Cap at 200
    tasks = TaskService.get_workspace_tasks(workspace_id, limit)
    return [_task_to_dict(t) for t in tasks]


@router.get("/workspace/{workspace_id}/stage/{stage}")
async def get_stage_tasks(workspace_id: str, stage: str) -> List[Dict[str, Any]]:
    """获取某 workspace 某 stage 的任务历史。"""
    tasks = TaskService.get_stage_tasks(workspace_id, stage)
    return [_task_to_dict(t) for t in tasks]


@router.get("/{task_id}/events")
async def get_task_events(task_id: str) -> Dict[str, Any]:
    """获取任务的 SSE 事件日志（用于回放）。"""
    task = TaskService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        events = json.loads(task.sse_events) if task.sse_events else []
    except (json.JSONDecodeError, ValueError):
        events = []
    return {
        "task_id": task.id,
        "stage": task.stage,
        "status": task.status,
        "event_count": len(events),
        "events": events,
    }


def _task_to_dict(task: PipelineTask) -> Dict[str, Any]:
    """将 PipelineTask 转为 API 响应字典。"""
    return {
        "id": task.id,
        "workspace_id": task.workspace_id,
        "stage": task.stage,
        "status": task.status,
        "mode": task.mode,
        "provider": task.provider,
        "model_name": task.model_name,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "output_summary": task.output_summary,
        "error_message": task.error_message,
        "total_chars": task.total_chars,
        "duration_seconds": task.duration_seconds,
    }
