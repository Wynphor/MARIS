"""
Comprehensive unit tests for MathModel-Engine backend services.

Covers: CompetitionConfigService, OutputPersistenceService, TaskService,
        StageRegistry, Prompts, and Exceptions.

Run: cd backend && python -m pytest tests/test_services.py -v --tb=short -x
"""
import json
import os
import sys
import shutil
import tempfile
import uuid

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.db.database import create_db_and_tables, engine
from sqlmodel import Session as DBSession, SQLModel


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _patch_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR to a temp directory so tests never touch real data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    # Also patch module-level DATA_DIR bindings in services
    from app.services import competition_config_service, latex_service, workspace_service
    monkeypatch.setattr(competition_config_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(latex_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(workspace_service, "DATA_DIR", data_dir)
    yield


@pytest.fixture()
def workspace_id():
    """Return a deterministic workspace id for test isolation."""
    return "test-ws-unit-001"


@pytest.fixture(autouse=True)
def _init_db():
    """Create all SQLModel tables before each test (idempotent)."""
    create_db_and_tables()
    yield


@pytest.fixture()
def client():
    """FastAPI TestClient for API-level tests."""
    from app.main import app
    with TestClient(app) as c:
        yield c


# ============================================================
# TestCompetitionConfigService
# ============================================================

class TestCompetitionConfigService:
    """Tests for CompetitionConfigService static methods."""

    def test_init_workspace_creates_dirs_and_config(self, workspace_id):
        from app.services.competition_config_service import (
            CompetitionConfigService, STANDARD_DIRS, DEFAULT_CONFIG,
        )

        result = CompetitionConfigService.init_workspace(workspace_id)
        ws = settings.DATA_DIR / workspace_id

        # All standard directories should exist
        for d in STANDARD_DIRS:
            assert (ws / d).is_dir(), f"Missing directory: {d}"

        # config.json should exist with default content
        config_path = ws / "config.json"
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["competition_type"] == DEFAULT_CONFIG["competition_type"]
        assert saved["language"] == "zh"
        assert result["config"] == DEFAULT_CONFIG

    def test_get_config_returns_defaults_when_missing(self, workspace_id):
        from app.services.competition_config_service import (
            CompetitionConfigService, DEFAULT_CONFIG,
        )

        # No workspace initialised -- should return defaults
        cfg = CompetitionConfigService.get_config("nonexistent-ws")
        assert cfg == DEFAULT_CONFIG

        # Corrupt JSON should also return defaults
        ws = settings.DATA_DIR / workspace_id
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "config.json").write_text("NOT JSON!!", encoding="utf-8")
        cfg2 = CompetitionConfigService.get_config(workspace_id)
        assert cfg2 == DEFAULT_CONFIG

    def test_update_config_merges_fields(self, workspace_id):
        from app.services.competition_config_service import (
            CompetitionConfigService, DEFAULT_CONFIG,
        )

        CompetitionConfigService.init_workspace(workspace_id)

        updates = {"team_name": "Alpha", "max_pages": 15, "bogus_key": "ignored"}
        result = CompetitionConfigService.update_config(workspace_id, updates)

        assert result["team_name"] == "Alpha"
        assert result["max_pages"] == 15
        # Unknown keys are ignored
        assert "bogus_key" not in result
        # Other defaults preserved
        assert result["language"] == DEFAULT_CONFIG["language"]


# ============================================================
# TestOutputPersistenceService
# ============================================================

class TestOutputPersistenceService:
    """Tests for OutputPersistenceService."""

    def test_save_code_files_extracts_python_blocks(self, workspace_id):
        from app.services.output_persistence_service import OutputPersistenceService

        ws_path = settings.DATA_DIR / workspace_id
        ws_path.mkdir(parents=True, exist_ok=True)

        ai_output = (
            "Here is the solution:\n\n"
            "```python\n"
            "import numpy as np\n\n"
            "def solve():\n"
            "    x = np.array([1, 2, 3, 4, 5])\n"
            "    y = np.array([2, 4, 6, 8, 10])\n"
            "    result = np.polyfit(x, y, 1)\n"
            "    return result\n\n"
            "if __name__ == '__main__':\n"
            "    print(solve())\n"
            "```\n"
        )
        saved = OutputPersistenceService._save_code_files(ws_path, ai_output)
        assert saved is not None
        assert Path(saved).exists()
        content = Path(saved).read_text(encoding="utf-8")
        assert "import numpy" in content
        assert "def solve" in content

    def test_save_latex_extracts_documentclass(self, workspace_id):
        from app.services.output_persistence_service import OutputPersistenceService

        ws_path = settings.DATA_DIR / workspace_id
        ws_path.mkdir(parents=True, exist_ok=True)

        ai_output = (
            "Below is the paper:\n\n"
            "```latex\n"
            "\\documentclass{article}\n"
            "\\usepackage{amsmath}\n"
            "\\begin{document}\n"
            "\\title{Test Paper}\n"
            "\\maketitle\n"
            "\\end{document}\n"
            "```\n"
        )
        saved = OutputPersistenceService._save_latex(ws_path, ai_output)
        assert saved is not None
        tex = Path(saved).read_text(encoding="utf-8")
        assert "\\documentclass" in tex
        assert "\\end{document}" in tex

    def test_save_declared_artifact_with_backup(self, workspace_id):
        from app.services.output_persistence_service import OutputPersistenceService

        ws_path = settings.DATA_DIR / workspace_id
        target = ws_path / "src" / "solve_all.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('old')\n", encoding="utf-8")

        ai_output = (
            "<artifact path=\"src/solve_all.py\">\n"
            "print('new')\n"
            "</artifact>"
        )
        saved = OutputPersistenceService.save_stage_output(workspace_id, "code-gen", ai_output)

        assert saved == str(target)
        assert target.read_text(encoding="utf-8") == "print('new')"
        assert target.with_suffix(".py.bak").read_text(encoding="utf-8") == "print('old')\n"

    def test_clean_output_strips_system_tags(self):
        from app.services.output_persistence_service import OutputPersistenceService

        raw = (
            "[TASK] abc-123\n"
            "[INFO] Starting...\n"
            "[STEP 1/3] Working\n"
            "This is actual content that is long enough to pass the minimum length check for cleaning.\n"
            "[DONE]\n"
            "[STATS] 100 chars\n"
        )
        cleaned = OutputPersistenceService._clean_output(raw)
        assert "[TASK]" not in cleaned
        assert "[INFO]" not in cleaned
        assert "[STEP" not in cleaned
        assert "[DONE]" not in cleaned
        assert "[STATS]" not in cleaned
        assert "actual content" in cleaned

    def test_stage_output_map_coverage(self):
        from app.services.output_persistence_service import STAGE_OUTPUT_MAP

        # Key stages should be present
        expected_stages = [
            "decompose", "model-select", "format-check", "claim-audit",
            "citation-audit", "review",
        ]
        for stage in expected_stages:
            assert stage in STAGE_OUTPUT_MAP, f"Missing stage: {stage}"

        # Stages that map to None (handled specially) should exist
        assert STAGE_OUTPUT_MAP.get("auto-fix") is None
        assert STAGE_OUTPUT_MAP.get("figure-gen") is None

        # Stages that map to a file should have .md or .tex extension
        for stage, path in STAGE_OUTPUT_MAP.items():
            if path is not None:
                assert path.endswith(".md"), f"Stage {stage} maps to non-md file: {path}"


# ============================================================
# TestTaskService
# ============================================================

class TestTaskService:
    """Tests for TaskService CRUD against real SQLite."""

    def test_create_and_get_task(self):
        from app.services.task_service import TaskService
        from app.models.pipeline import PipelineTask

        ws = f"ws-task-{uuid.uuid4().hex[:8]}"
        task = TaskService.create_task(
            workspace_id=ws,
            stage="decompose",
            mode="API",
            provider="deepseek",
            model_name="deepseek-chat",
        )
        assert task.id is not None
        assert task.status == "PENDING"
        assert task.stage == "decompose"

        fetched = TaskService.get_task(task.id)
        assert fetched is not None
        assert fetched.id == task.id
        assert fetched.workspace_id == ws

        # Non-existent id returns None
        assert TaskService.get_task("no-such-id") is None

    def test_update_task_status(self):
        from app.services.task_service import TaskService

        ws = f"ws-update-{uuid.uuid4().hex[:8]}"
        task = TaskService.create_task(
            workspace_id=ws, stage="write",
        )
        assert task.status == "PENDING"

        task.mark_running()
        TaskService.update_task(task)
        refreshed = TaskService.get_task(task.id)
        assert refreshed.status == "RUNNING"
        assert refreshed.started_at is not None

        task.mark_completed("Output summary text")
        TaskService.update_task(task)
        refreshed2 = TaskService.get_task(task.id)
        assert refreshed2.status == "COMPLETED"
        assert refreshed2.output_summary == "Output summary text"

        # Test mark_failed path
        task2 = TaskService.create_task(
            workspace_id=ws, stage="code-gen",
        )
        task2.mark_running()
        task2.mark_failed("Something broke")
        TaskService.update_task(task2)
        refreshed3 = TaskService.get_task(task2.id)
        assert refreshed3.status == "FAILED"
        assert refreshed3.error_message == "Something broke"

    def test_get_workspace_tasks_ordered(self):
        from app.services.task_service import TaskService

        ws = f"ws-order-{uuid.uuid4().hex[:8]}"
        t1 = TaskService.create_task(workspace_id=ws, stage="decompose")
        t2 = TaskService.create_task(workspace_id=ws, stage="model-select")
        t3 = TaskService.create_task(workspace_id=ws, stage="write")

        tasks = TaskService.get_workspace_tasks(ws)
        assert len(tasks) == 3
        # Newest first (created_at desc)
        ids_returned = [t.id for t in tasks]
        assert t3.id == ids_returned[0]
        assert t1.id == ids_returned[-1]

        # Limit works
        limited = TaskService.get_workspace_tasks(ws, limit=2)
        assert len(limited) == 2


# ============================================================
# TestStageRegistry
# ============================================================

class TestStageRegistry:
    """Tests for stage_registry dependency logic."""

    def test_check_dependencies_passes_with_met_deps(self):
        from app.services.stage_registry import check_dependencies
        from app.models.workspace import Workspace

        # model-select depends on decompose. Status DECOMPOSED satisfies that.
        ws = Workspace(
            id="ws-dep-pass", title="t", question_id="Q1",
            problem_type="opt", status="DECOMPOSED",
        )
        # Should not raise
        check_dependencies(ws, "model-select")

    def test_check_dependencies_uses_explicit_completed_stages(self):
        from app.services.stage_registry import check_dependencies
        from app.models.workspace import Workspace

        ws = Workspace(
            id="ws-explicit-stage", title="t", question_id="Q1",
            problem_type="opt", status="INIT",
        )
        ws.mark_stage_completed("decompose")

        # Explicit completion should satisfy dependencies even if coarse status lags.
        check_dependencies(ws, "model-select")

    def test_check_dependencies_fails_with_unmet_deps(self):
        from app.services.stage_registry import check_dependencies
        from app.models.workspace import Workspace
        from fastapi import HTTPException

        # model-select depends on decompose, but status is INIT (decompose not done)
        ws = Workspace(
            id="ws-dep-fail", title="t", question_id="Q1",
            problem_type="opt", status="INIT",
        )
        with pytest.raises(HTTPException) as exc_info:
            check_dependencies(ws, "model-select")
        assert exc_info.value.status_code == 422
        assert "decompose" in exc_info.value.detail

    def test_get_completed_stages(self):
        from app.services.stage_registry import (
            get_completed_stages, DEFAULT_PIPELINE_ORDER,
        )

        # If status is WRITTEN, decompose/model-select/write are done
        done = get_completed_stages(DEFAULT_PIPELINE_ORDER, "WRITTEN")
        assert "decompose" in done
        assert "model-select" in done
        assert "write" in done
        # review is after write, so not done yet
        assert "review" not in done

        # Branch stages can be represented explicitly.
        done_with_branch = get_completed_stages(
            DEFAULT_PIPELINE_ORDER + ["paper-ref"],
            "INIT",
            '["paper-ref"]',
        )
        assert "paper-ref" in done_with_branch

        # INIT status -- nothing done
        done_init = get_completed_stages(DEFAULT_PIPELINE_ORDER, "INIT")
        assert len(done_init) == 0

    def test_stage_dependencies_consistency(self):
        from app.services.stage_registry import STAGE_DEPENDENCIES, get_stage_stream

        # Every stage listed in STAGE_DEPENDENCIES should have a handler
        # in get_stage_stream (or at least not crash when queried).
        # We just verify the dict is non-empty and keys are strings.
        assert len(STAGE_DEPENDENCIES) > 0
        for stage, deps in STAGE_DEPENDENCIES.items():
            assert isinstance(stage, str), f"Stage key is not a string: {stage}"
            assert isinstance(deps, list), f"Deps for {stage} is not a list"
            for dep in deps:
                assert dep in STAGE_DEPENDENCIES, (
                    f"Stage '{stage}' depends on '{dep}' which is not in STAGE_DEPENDENCIES"
                )


# ============================================================
# TestPrompts
# ============================================================

class TestPrompts:
    """Tests for prompt building functions and model routing."""

    def test_build_decompose_prompt_structure(self):
        from app.core.prompts import build_decompose_prompt

        system, user = build_decompose_prompt("ws-001", "某工厂生产两种产品...")
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 100, "System prompt should be substantial"
        # Workspace id and problem text injected into user prompt
        assert "ws-001" in user
        assert "某工厂" in user
        # Key structural elements present
        assert "拆解" in system
        assert "子问题" in system or "子问题" in user

    def test_get_model_for_stage_known(self):
        from app.core.prompts import get_model_for_stage

        result = get_model_for_stage("decompose")
        assert result["provider"] == "deepseek"
        assert result["model"] == "deepseek-chat"

        result2 = get_model_for_stage("preprocess")
        assert result2["provider"] == "mimo"

    def test_get_model_for_stage_unknown_fallback(self):
        from app.core.prompts import get_model_for_stage

        result = get_model_for_stage("totally-unknown-stage")
        assert result["provider"] == "deepseek"
        assert result["model"] == "deepseek-chat"

    def test_task_model_map_completeness(self):
        from app.core.prompts import TASK_MODEL_MAP

        # Core pipeline stages should all be present
        required = [
            "decompose", "model-select", "code-gen", "write",
            "review", "format-check", "preprocess",
        ]
        for stage in required:
            assert stage in TASK_MODEL_MAP, f"Missing stage in TASK_MODEL_MAP: {stage}"
            entry = TASK_MODEL_MAP[stage]
            assert "provider" in entry
            assert "model" in entry


# ============================================================
# TestExceptions
# ============================================================

class TestExceptions:
    """Tests for exception classes and error handlers."""

    def test_not_found_error_response(self):
        from app.core.exceptions import NotFoundError

        err = NotFoundError(message="Workspace not found")
        resp = err.to_response()
        assert resp.status_code == 404
        body = json.loads(resp.body)
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message"] == "Workspace not found"

    def test_validation_error_response(self):
        from app.core.exceptions import ValidationError

        err = ValidationError(message="Bad field", details={"field": "title"})
        resp = err.to_response()
        assert resp.status_code == 422
        body = json.loads(resp.body)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["details"]["field"] == "title"

    def test_generic_handler_returns_500(self):
        """The global exception handler should catch unhandled errors and return 500."""
        import asyncio
        from app.core.exceptions import generic_error_handler
        from starlette.requests import Request

        # Build a minimal fake Request
        scope = {"type": "http", "method": "GET", "path": "/boom"}
        request = Request(scope)

        resp = asyncio.run(
            generic_error_handler(request, RuntimeError("deliberate crash"))
        )
        assert resp.status_code == 500
        body = json.loads(resp.body)
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "deliberate crash" not in body["error"]["message"]
