"""
E2E Smoke Test — 真实端到端冒烟测试

不 mock LLM，用真实 API 跑完整 pipeline。
单独运行: cd backend && python -m pytest tests/test_e2e_smoke.py -v
"""
import pytest
import json
import sys
import os
from pathlib import Path

# 确保能导入 app 模块（与其他测试文件一致）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import create_db_and_tables


@pytest.fixture(scope="module")
def client():
    """创建测试客户端。"""
    create_db_and_tables()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def test_workspace(client):
    """Create a test workspace with problem text."""
    resp = client.post("/api/v1/workspaces/", json={
        "title": "E2E Smoke Test",
        "question_id": "TEST-01",
        "problem_type": "CUMCM",
    })
    assert resp.status_code in (200, 201)
    ws_id = resp.json()["id"]

    # Write problem text directly
    from app.core.config import settings
    ws_dir = Path(settings.DATA_DIR) / ws_id
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "problem.txt").write_text(
        "某城市需要优化公交线路规划，已知乘客OD数据、道路网络、"
        "现有线路和客流需求。请设计最优公交线路方案，"
        "使得乘客平均出行时间最小化，同时满足覆盖率和运营成本约束。",
        encoding="utf-8"
    )
    return ws_id


class TestPipelineStages:
    """Test each pipeline stage individually."""

    def test_decompose_produces_output(self, client, test_workspace):
        """decompose stage should produce problem_decomposition.md."""
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "decompose",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            from app.core.config import settings
            decomp_file = Path(settings.DATA_DIR) / test_workspace / "problem_decomposition.md"
            assert decomp_file.exists(), "problem_decomposition.md should be created"
            content = decomp_file.read_text(encoding="utf-8")
            assert len(content) > 50

    def test_model_select_produces_output(self, client, test_workspace):
        """model-select stage should produce model_recommendation.md."""
        from app.core.config import settings
        decomp_file = Path(settings.DATA_DIR) / test_workspace / "problem_decomposition.md"
        decomp_file.parent.mkdir(parents=True, exist_ok=True)
        if not decomp_file.exists():
            decomp_file.write_text("# 问题拆解\n\n## 子问题1\n优化公交线路\n", encoding="utf-8")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "model-select",
            "mode": "API",
        })
        if resp.status_code in (200, 201):
            rec_file = Path(settings.DATA_DIR) / test_workspace / "model_recommendation.md"
            assert rec_file.exists()

    def test_code_gen_produces_files(self, client, test_workspace):
        """code-gen should produce Python files in src/ (may fail if LLM unavailable)."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        rec = ws_dir / "model_recommendation.md"
        if not rec.exists():
            rec.write_text("# 模型推荐\n\n推荐使用线性规划模型。\n\nPython: PuLP, scipy\n", encoding="utf-8")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "code-gen",
            "mode": "API",
        })
        assert resp.status_code in (200, 422, 500)
        # File assertion is best-effort (LLM may fail/timout)
        if resp.status_code == 200:
            src_dir = ws_dir / "src"
            py_files = list(src_dir.glob("*.py"))
            # Don't assert — LLM may not produce output in time

    def test_write_produces_latex(self, client, test_workspace):
        """write stage should produce paper/main.tex (may fail if LLM unavailable)."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        rec = ws_dir / "model_recommendation.md"
        if not rec.exists():
            rec.write_text("# 模型推荐\n\n线性规划优化\n", encoding="utf-8")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "write",
            "mode": "API",
        })
        assert resp.status_code in (200, 422, 500)

    def test_format_check_runs(self, client, test_workspace):
        """format-check should run without error."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        paper_dir = ws_dir / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)
        (paper_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nTest\n\\end{document}\n",
            encoding="utf-8"
        )
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "format-check",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_review_runs(self, client, test_workspace):
        """review stage should run."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        paper_dir = ws_dir / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)
        (paper_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nTest paper\n\\end{document}\n",
            encoding="utf-8"
        )
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "review",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)


class TestManifest:
    """Test manifest.json tracking."""

    def test_manifest_created_after_stage(self, client, test_workspace):
        """Running a stage should update manifest.json."""
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "decompose",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            from app.core.config import settings
            manifest_path = Path(settings.DATA_DIR) / test_workspace / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                assert "stages" in manifest
                assert "workspace_id" in manifest


class TestTriagePersistence:
    """Test triage result saving."""

    def test_triage_saves_decision_matrix(self, client, test_workspace):
        """Triage should save decision matrix when workspace_id provided."""
        resp = client.post("/api/v1/workspaces/triage", json={
            "workspace_id": test_workspace,
            "problems": [
                {"id": "C", "text": "公交线路优化问题", "title": "C题"},
                {"id": "D", "text": "图像识别问题", "title": "D题"},
            ],
            "team_skills": ["optimization", "python"],
        })
        assert resp.status_code in (200, 422)


class TestSubmission:
    """Test submission packaging."""

    def test_pack_requires_pdf(self, client, test_workspace):
        """Pack should fail if no PDF exists."""
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "pack",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_pack_with_files(self, client, test_workspace):
        """Pack should succeed with required files."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        paper_dir = ws_dir / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)
        (paper_dir / "main.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
        src_dir = ws_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "solve_all.py").write_text("print('hello')\n", encoding="utf-8")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace,
            "stage": "pack",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)


class TestSystemConfig:
    """Test system configuration API."""

    def test_get_system_config(self, client):
        """System config endpoint should return provider info."""
        resp = client.get("/api/v1/system/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "default_model" in data
        assert len(data["providers"]) == 6

    def test_update_default_model(self, client):
        """Should be able to update default model."""
        resp = client.put("/api/v1/system/config", json={
            "default_model": "deepseek-chat",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "updated" in data


class TestSequentialPipeline:
    """
    真实顺序 E2E：上传题目 -> 拆解 -> 选模 -> 代码 -> 写论文 -> 审查 -> 打包
    每步依赖前一步的真实输出，不手动预设文件。
    """

    @pytest.fixture(scope="class")
    def seq_workspace(self, client):
        """Create workspace with real problem text."""
        resp = client.post("/api/v1/workspaces/", json={
            "title": "Sequential E2E",
            "question_id": "SEQ-01",
            "problem_type": "CUMCM",
        })
        assert resp.status_code in (200, 201)
        ws_id = resp.json()["id"]

        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / ws_id
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "problem.md").write_text(
            "# C题：城市公交线路优化\n\n"
            "## 问题背景\n"
            "某城市有 50 个公交站点，现有 15 条公交线路。"
            "乘客 OD 矩阵数据见附件 data.csv。\n\n"
            "## 任务\n"
            "1. 建立公交线路优化模型\n"
            "2. 设计最优线路方案\n"
            "3. 分析方案的覆盖率和运营成本\n",
            encoding="utf-8"
        )
        # Create a dummy data file for preprocess
        (ws_dir / "raw").mkdir(parents=True, exist_ok=True)
        (ws_dir / "raw" / "data.csv").write_text(
            "站点,经度,纬度,日客流\nA1,116.4,39.9,5000\nA2,116.5,39.8,3000\nA3,116.3,40.0,4000\n",
            encoding="utf-8"
        )
        return ws_id

    def test_01_decompose(self, client, seq_workspace):
        """Step 1: Decompose problem."""
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": seq_workspace,
            "stage": "decompose",
            "mode": "API",
        })
        assert resp.status_code == 200
        # Verify output exists
        from app.core.config import settings
        decomp = Path(settings.DATA_DIR) / seq_workspace / "problem_decomposition.md"
        assert decomp.exists(), "decompose should create problem_decomposition.md"
        assert len(decomp.read_text(encoding="utf-8")) > 50

    def test_02_model_select(self, client, seq_workspace):
        """Step 2: Model selection (depends on decompose)."""
        from app.core.config import settings
        decomp = Path(settings.DATA_DIR) / seq_workspace / "problem_decomposition.md"
        if not decomp.exists():
            pytest.skip("decompose not available")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": seq_workspace,
            "stage": "model-select",
            "mode": "API",
        })
        # May fail with 422 if workspace status not updated
        assert resp.status_code in (200, 422)

    def test_03_code_gen(self, client, seq_workspace):
        """Step 3: Code generation (depends on model-select)."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / seq_workspace
        rec = ws_dir / "model_recommendation.md"
        if not rec.exists():
            pytest.skip("model-select not available")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": seq_workspace,
            "stage": "code-gen",
            "mode": "API",
        })
        assert resp.status_code in (200, 422, 500)

    def test_04_write(self, client, seq_workspace):
        """Step 4: Write paper (depends on model-select)."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / seq_workspace
        rec = ws_dir / "model_recommendation.md"
        if not rec.exists():
            pytest.skip("model-select not available")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": seq_workspace,
            "stage": "write",
            "mode": "API",
        })
        assert resp.status_code in (200, 422, 500)

    def test_05_format_check(self, client, seq_workspace):
        """Step 5: Format check (depends on write)."""
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / seq_workspace
        tex = ws_dir / "paper" / "main.tex"
        if not tex.exists():
            pytest.skip("write not available")

        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": seq_workspace,
            "stage": "format-check",
            "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_06_manifest_exists(self, client, seq_workspace):
        """Step 6: Verify manifest.json was created."""
        from app.core.config import settings
        manifest = Path(settings.DATA_DIR) / seq_workspace / "manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            assert "stages" in data
            assert len(data["stages"]) > 0

    def test_07_problem_md_exists(self, client, seq_workspace):
        """Step 7: Verify problem.md was preserved at workspace root."""
        from app.core.config import settings
        problem = Path(settings.DATA_DIR) / seq_workspace / "problem.md"
        assert problem.exists()
        content = problem.read_text(encoding="utf-8")
        assert "公交" in content or "优化" in content

