"""
Fast E2E Tests — 不调用 LLM 的快速接口测试

运行: cd backend && python -m pytest tests/test_e2e_fast.py -v
预期: < 30 秒
"""
import pytest
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import create_db_and_tables


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def test_workspace(client):
    resp = client.post("/api/v1/workspaces/", json={
        "title": "Fast E2E Test",
        "question_id": "FAST-01",
        "problem_type": "CUMCM",
    })
    assert resp.status_code in (200, 201)
    ws_id = resp.json()["id"]

    from app.core.config import settings
    ws_dir = Path(settings.DATA_DIR) / ws_id
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "problem.md").write_text("# Test Problem\n优化公交线路\n", encoding="utf-8")
    return ws_id


class TestHealthAndConfig:
    """Health and system config endpoints."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ready(self, client):
        resp = client.get("/ready")
        assert resp.status_code in (200, 503)

    def test_system_config(self, client):
        resp = client.get("/api/v1/system/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) == 6
        assert "default_model" in data

    def test_update_default_model(self, client):
        resp = client.put("/api/v1/system/config", json={"default_model": "deepseek-chat"})
        assert resp.status_code == 200

    def test_pipeline_stages(self, client):
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        stages = resp.json()["stages"]
        assert len(stages) > 10


class TestWorkspace:
    """Workspace CRUD."""

    def test_list_workspaces(self, client):
        resp = client.get("/api/v1/workspaces/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_config(self, client, test_workspace):
        resp = client.get(f"/api/v1/workspaces/{test_workspace}/config")
        assert resp.status_code == 200
        assert "competition_type" in resp.json()

    def test_update_config(self, client, test_workspace):
        resp = client.put(f"/api/v1/workspaces/{test_workspace}/config", json={
            "competition_type": "国赛", "review_rounds": 3,
        })
        assert resp.status_code == 200

    def test_dashboard(self, client, test_workspace):
        resp = client.get(f"/api/v1/workspaces/{test_workspace}/dashboard")
        assert resp.status_code == 200

    def test_file_tree(self, client, test_workspace):
        resp = client.get(f"/api/v1/workspaces/{test_workspace}/tree")
        assert resp.status_code == 200


class TestSubmission:
    """Submission packing (no LLM needed)."""

    def test_pack_no_pdf(self, client, test_workspace):
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace, "stage": "pack", "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_pack_with_files(self, client, test_workspace):
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        (ws_dir / "paper").mkdir(parents=True, exist_ok=True)
        (ws_dir / "paper" / "main.pdf").write_bytes(b"%PDF-1.4 fake")
        (ws_dir / "src").mkdir(parents=True, exist_ok=True)
        (ws_dir / "src" / "solve_all.py").write_text("print('ok')\n")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace, "stage": "pack", "mode": "API",
        })
        assert resp.status_code in (200, 422)


class TestDeterministicChecks:
    """Tests that don't need LLM — format check, manifest."""

    def test_format_check_deterministic(self, client, test_workspace):
        from app.core.config import settings
        ws_dir = Path(settings.DATA_DIR) / test_workspace
        (ws_dir / "paper").mkdir(parents=True, exist_ok=True)
        (ws_dir / "paper" / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nTest\n\\end{document}\n",
            encoding="utf-8"
        )
        # format-check does deterministic check first, then LLM
        # We just verify it doesn't crash
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": test_workspace, "stage": "format-check", "mode": "API",
        })
        assert resp.status_code in (200, 422)

    def test_manifest_structure(self, client, test_workspace):
        """Verify manifest.json has required fields."""
        from app.core.config import settings
        from app.services.output_persistence_service import OutputPersistenceService
        manifest = OutputPersistenceService.get_manifest(test_workspace)
        assert "workspace_id" in manifest
        assert "stages" in manifest

    def test_format_profiles_exist(self):
        from app.core.format_profiles import FORMAT_PROFILES, check_latex_compliance
        assert len(FORMAT_PROFILES) >= 5
        result = check_latex_compliance(
            "\\documentclass{article}\\begin{document}\\end{document}", "国赛"
        )
        assert "passed" in result
        assert "issues" in result

    def test_model_knowledge_search(self):
        from app.services.model_knowledge_base import search_models, search_by_formula, FORMULA_INDEX
        results = search_models("预测")
        assert len(results) > 0
        assert len(FORMULA_INDEX) > 10

    def test_submission_profiles(self):
        from app.services.submission_service import CONTEST_PROFILES
        assert "CUMCM" in CONTEST_PROFILES
        assert CONTEST_PROFILES["CUMCM"]["preferred_format"] == "rar"
