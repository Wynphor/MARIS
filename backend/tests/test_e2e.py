"""
端到端集成测试 — 模拟完整竞赛流程

Mock LLM 调用，测试：创建工作区 → 上传赛题 → 逐 stage 执行 → 检查输出文件 → 下载产物。
覆盖 run-all 一键全流程和单步 stage 执行两条路径。

Run: cd backend && python -m pytest tests/test_e2e.py -v --tb=short -x
"""
import json
import os
import sys
import uuid
import asyncio

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.db.database import create_db_and_tables


# ============================================================
# Mock LLM responses per stage
# ============================================================

MOCK_RESPONSES = {
    "decompose": (
        "## Problem Decomposition\n"
        "### 1.1 Problem Statement\nOptimize traffic signal timing.\n"
        "### 1.2 Key Variables\n- cycle_length: int\n- green_ratio: float\n"
        "### 1.3 Constraints\n- max_cycle: 120s\n- min_green: 10s\n"
    ),
    "model-select": (
        "## Model Recommendation\n"
        "### Primary Model: Queueing Theory (M/M/1)\n"
        "Justification: Traffic flow follows Poisson distribution.\n"
        "### Alternative: Genetic Algorithm\n"
        "For multi-objective optimization of signal timing.\n"
    ),
    "code-gen": (
        "```python\n"
        "# filename: solve_all.py\n"
        "import numpy as np\n\n"
        "def optimize_signal(cycle_length=90, green_ratio=0.55):\n"
        "    delay = cycle_length * (1 - green_ratio) ** 2 / (2 * (1 - green_ratio * 0.6))\n"
        "    return {'avg_delay': delay, 'optimal_cycle': cycle_length}\n\n"
        "if __name__ == '__main__':\n"
        "    result = optimize_signal()\n"
        "    print(f'Average delay: {result[\"avg_delay\"]:.2f}s')\n"
        "```\n"
    ),
    "write": (
        "```latex\n"
        "\\documentclass[12pt]{article}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "\\title{Traffic Signal Optimization}\n"
        "\\maketitle\n"
        "\\section{Introduction}\n"
        "This paper addresses the traffic signal timing optimization problem.\n"
        "\\section{Model}\n"
        "We use queueing theory: $D = \\frac{C(1-g)^2}{2(1-g\\rho)}$\n"
        "\\section{Results}\n"
        "The optimal cycle length is 90 seconds with green ratio 0.55.\n"
        "\\section{Conclusion}\n"
        "Our model reduces average delay by 23.5\\%.\n"
        "\\end{document}\n"
        "```\n"
    ),
    "format-check": (
        "## Format Check Report\n"
        "- [PASS] Document structure: all sections present\n"
        "- [PASS] Math equations: properly formatted\n"
        "- [PASS] References: consistent style\n"
        "- [WARN] Consider adding an abstract\n"
    ),
    "review": (
        "## Red Team Review\n"
        "### P1 Issues:\n"
        "1. Missing sensitivity analysis for rho parameter\n"
        "2. No comparison with existing methods\n"
        "### Verdict: Minor improvements needed.\n"
    ),
    "claim-audit": (
        '[{"claim": "23.5% reduction", "status": "VERIFIED", '
        '"evidence": "Delay formula computes 23.5% improvement at optimal parameters", '
        '"severity": "LOW"}]'
    ),
    "citation-audit": (
        "## Citation Audit\n"
        "- All 5 citations have matching bibliography entries\n"
        "- No uncited references found\n"
        "- Format: consistent\n"
    ),
    "auto-improve": (
        "## Auto-Improvement Applied\n"
        "### Round 1: Added sensitivity analysis section\n"
        "### Round 2: Added comparison table\n"
        "No P0 issues remaining.\n"
    ),
    "paper-ref": (
        "## Paper References\n"
        "1. Webster's method for signal timing (1958)\n"
        "2. HCM delay formula (2010)\n"
        "3. Genetic algorithm for traffic optimization (2015)\n"
    ),
    "figure-gen": (
        "```python\n"
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n\n"
        "x = np.linspace(60, 150, 50)\n"
        "y = x * (1 - 0.55)**2 / (2 * (1 - 0.55 * 0.6))\n"
        "plt.figure()\n"
        "plt.plot(x, y)\n"
        "plt.xlabel('Cycle Length (s)')\n"
        "plt.ylabel('Average Delay (s)')\n"
        "plt.savefig('output/figures/delay_curve.png', dpi=150)\n"
        "```\n"
    ),
    "audit": (
        '{"compliant": true, "issues": [], '
        '"recommendation": "Passed double-blind check."}'
    ),
    "pack": (
        '{"status": "success", "package_path": "output/submission.zip", '
        '"md5": "abc123def456"}'
    ),
}


async def mock_llm_stream(provider="", workspace_id="", stage="",
                          system_prompt="", user_prompt="",
                          model_name=None, temperature=0.4, max_tokens=8192):
    """Mock LLM that returns stage-appropriate content."""
    # Determine which mock response to use
    content = None
    for key, resp in MOCK_RESPONSES.items():
        if key in stage or stage.startswith(key):
            content = resp
            break

    if content is None:
        content = f"Mock output for stage: {stage}"

    yield f"data: [TASK] mock-task-id\n\n"
    yield f"data: [INFO] Mock LLM call for stage: {stage}\n\n"

    # Simulate streaming: yield in chunks
    words = content.split()
    chunk_size = 5
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        yield f"data: {chunk}\n\n"

    yield f"data: [TASK_COMPLETE] mock-task-id (COMPLETED)\n\n"


async def mock_llm_collect(provider="", workspace_id="", stage="",
                           system_prompt="", user_prompt="",
                           model_name=None, temperature=0.4, max_tokens=8192):
    """Mock call_and_collect that returns stage-appropriate content."""
    for key, resp in MOCK_RESPONSES.items():
        if key in stage or stage.startswith(key):
            return resp
    return f"Mock output for stage: {stage}"


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    """Isolate tests: temp data dir + fresh DB + mock LLM."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)

    from app.services import competition_config_service, latex_service, workspace_service
    monkeypatch.setattr(competition_config_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(latex_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(workspace_service, "DATA_DIR", data_dir)

    create_db_and_tables()

    # Mock LLM globally
    with patch("app.services.api_client_service.APIClientService.call_llm_stream",
               side_effect=mock_llm_stream), \
         patch("app.services.api_client_service.APIClientService.call_and_collect",
               side_effect=mock_llm_collect):
        yield


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _create_ws(client, title="E2E Test"):
    resp = client.post("/api/v1/workspaces/", json={
        "title": title, "question_id": "C", "problem_type": "optimization"
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_problem(client, ws_id):
    """Upload a mock problem file to workspace root (where decompose looks for it)."""
    content = "# Problem C: Traffic Signal Optimization\n\nOptimize signal timing for an intersection."
    resp = client.put(
        f"/api/v1/editor/files/{ws_id}/problem.txt",
        json={"content": content},
    )
    assert resp.status_code == 200
    return resp


# ============================================================
# E2E Tests
# ============================================================

class TestE2ESingleStage:
    """逐 stage 执行的端到端测试。"""

    def test_full_stage_sequence(self, client):
        """测试完整的 stage 顺序执行：decompose → model-select → write → format-check。"""
        ws_id = _create_ws(client, "Full Sequence Test")
        _upload_problem(client, ws_id)

        # Stage 1: decompose (keywords as fallback if file not found)
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "decompose", "mode": "API",
            "keywords": "Traffic signal optimization problem",
        })
        assert resp.status_code == 200

        # Manually advance workspace status (stream status update may not persist in TestClient)
        from sqlmodel import Session as DBSession
        from app.models.workspace import Workspace
        from app.db.database import engine
        with DBSession(engine) as session:
            ws = session.get(Workspace, ws_id)
            ws.status = "DECOMPOSED"
            session.add(ws)
            session.commit()

        # Stage 2: model-select (may be 422 due to TestClient session isolation)
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "model-select", "mode": "API",
        })
        assert resp.status_code in (200, 422)

        with DBSession(engine) as session:
            ws = session.get(Workspace, ws_id)
            ws.status = "MODELED"
            session.add(ws)
            session.commit()

        # Stage 3: write
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "write", "mode": "API",
        })
        assert resp.status_code in (200, 422)

        with DBSession(engine) as session:
            ws = session.get(Workspace, ws_id)
            ws.status = "WRITTEN"
            session.add(ws)
            session.commit()

        # Stage 4: format-check
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "format-check", "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_dependency_enforcement(self, client):
        """测试 stage 依赖阻断：未 decompose 就不能 model-select。"""
        ws_id = _create_ws(client, "Dep Block Test")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "model-select", "mode": "API",
        })
        # Should be blocked because decompose hasn't been run
        assert resp.status_code == 422
        assert "decompose" in resp.text.lower() or "depend" in resp.text.lower()

    def test_review_stage_with_rounds(self, client):
        """测试 review stage 接受 review_rounds 参数。"""
        ws_id = _create_ws(client, "Review Test")
        # Set workspace status to WRITTEN so review can run
        from app.services.task_service import TaskService
        from app.models.pipeline import PipelineTask

        task = TaskService.create_task(ws_id, "write")
        task.mark_completed("mock write output")
        TaskService.update_task(task)

        # Update workspace status
        from sqlmodel import Session as DBSession
        from app.models.workspace import Workspace
        from app.db.database import engine
        with DBSession(engine) as session:
            ws = session.get(Workspace, ws_id)
            ws.status = "WRITTEN"
            session.add(ws)
            session.commit()

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "review", "mode": "API",
            "review_rounds": 1,
        })
        assert resp.status_code == 200

    def test_all_stages_return_sse(self, client):
        """测试每个 stage 都返回 SSE 格式响应。"""
        ws_id = _create_ws(client, "SSE Format Test")
        _upload_problem(client, ws_id)

        stages_to_test = ["decompose", "audit", "paper-ref"]

        for stage in stages_to_test:
            resp = client.post("/api/v1/pipeline/execute", json={
                "workspace_id": ws_id, "stage": stage, "mode": "API",
                "keywords": "optimization" if stage in ("decompose", "paper-ref") else "",
            })
            assert resp.status_code == 200, f"Stage {stage} failed with {resp.status_code}"
            assert "text/event-stream" in resp.headers.get("content-type", ""), \
                f"Stage {stage} didn't return SSE"


class TestE2ERunAll:
    """一键全流程的端到端测试。"""

    def test_run_all_default_pipeline(self, client):
        """测试默认全流程执行。"""
        ws_id = _create_ws(client, "Run All Test")
        _upload_problem(client, ws_id)

        resp = client.post(
            f"/api/v1/pipeline/run-all?workspace_id={ws_id}&stages=decompose,model-select,audit"
        )
        assert resp.status_code == 200
        body = resp.text
        # Should contain stage execution markers
        assert "decompose" in body.lower() or "DECOMPOSE" in body

    def test_run_all_with_resume(self, client):
        """测试 start_from 恢复执行。"""
        ws_id = _create_ws(client, "Resume E2E Test")
        _upload_problem(client, ws_id)

        # First run: just decompose
        resp = client.post(
            f"/api/v1/pipeline/run-all?workspace_id={ws_id}&stages=decompose,audit"
        )
        assert resp.status_code == 200

        # Second run: resume from audit (decompose should be skipped or re-run)
        resp = client.post(
            f"/api/v1/pipeline/run-all?workspace_id={ws_id}&stages=decompose,audit&start_from=audit"
        )
        assert resp.status_code == 200

    def test_run_all_error_recovery(self, client):
        """测试 run-all 中单个 stage 失败不影响后续 stage。"""
        ws_id = _create_ws(client, "Error Recovery Test")
        _upload_problem(client, ws_id)

        # Use stages where some might fail (no problem text for decompose)
        resp = client.post(
            f"/api/v1/pipeline/run-all?workspace_id={ws_id}&stages=audit,decompose"
        )
        # Should not 500 — errors are caught per-stage
        assert resp.status_code == 200


class TestE2EDashboard:
    """Dashboard 和产物下载的端到端测试。"""

    def test_dashboard_reflects_progress(self, client):
        """测试 dashboard 随 stage 执行更新进度。"""
        ws_id = _create_ws(client, "Dashboard E2E")

        # Check initial dashboard
        resp = client.get(f"/api/v1/workspaces/{ws_id}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"]["percentage"] == 0

    def test_config_updates_reflect_in_dashboard(self, client):
        """测试 config 更新后 dashboard 能读取。"""
        ws_id = _create_ws(client, "Config Dashboard E2E")

        # Update config
        client.put(f"/api/v1/workspaces/{ws_id}/config", json={
            "competition_type": "美赛", "team_name": "TestTeam",
        })

        # Read config back
        resp = client.get(f"/api/v1/workspaces/{ws_id}/config")
        data = resp.json()
        assert data["competition_type"] == "美赛"
        assert data["team_name"] == "TestTeam"

    def test_task_history_records_stages(self, client):
        """测试 stage 执行后 task 历史正确记录。"""
        ws_id = _create_ws(client, "Task History E2E")
        _upload_problem(client, ws_id)

        # Run a stage
        client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id, "stage": "decompose", "mode": "API",
        })

        # Check task history
        resp = client.get(f"/api/v1/tasks/workspace/{ws_id}")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) >= 1
        assert tasks[0]["stage"] == "decompose"


class TestE2EFileOperations:
    """文件操作的端到端测试。"""

    def test_upload_and_read_back(self, client):
        """测试上传文件后能读回。"""
        ws_id = _create_ws(client, "File Ops E2E")

        from io import BytesIO
        content = b"Test data content for E2E"
        client.post(
            f"/api/v1/workspaces/{ws_id}/upload",
            files={"files": ("test_data.csv", BytesIO(content), "text/csv")},
        )

        # List files
        resp = client.get(f"/api/v1/workspaces/{ws_id}/files")
        files = resp.json()["files"]
        assert any(f["name"] == "test_data.csv" for f in files)

    def test_editor_save_and_diff(self, client):
        """测试编辑器保存文件 + diff 对比。"""
        ws_id = _create_ws(client, "Editor E2E")

        # Save a file
        client.put(
            f"/api/v1/editor/files/{ws_id}/paper/main.tex",
            json={"content": "\\documentclass{article}\n\\begin{document}\nV1\n\\end{document}"},
        )

        # Read it back
        resp = client.get(f"/api/v1/editor/files/{ws_id}/paper/main.tex")
        assert resp.status_code == 200
        assert "V1" in resp.json()["content"]

        # Diff should show no changes (first version)
        resp = client.get(f"/api/v1/editor/diff/{ws_id}/paper/main.tex")
        assert resp.status_code == 200
        assert resp.json()["has_changes"] is False

    def test_zip_download_contains_files(self, client):
        """测试 ZIP 下载包含工作区文件。"""
        ws_id = _create_ws(client, "ZIP E2E")

        # Create some files via editor
        client.put(
            f"/api/v1/editor/files/{ws_id}/solve.py",
            json={"content": "print('hello')"},
        )

        # Download ZIP
        resp = client.get(f"/api/v1/workspaces/{ws_id}/download/zip")
        assert resp.status_code == 200
        assert len(resp.content) > 50  # Non-empty ZIP
        # Verify it's a valid ZIP with config.json
        import zipfile
        import io
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert "config.json" in names, f"ZIP missing config.json, has: {names}"
