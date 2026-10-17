"""
UX Feature Tests — config, download, diff, stages, resume
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import create_db_and_tables

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    create_db_and_tables()
    yield


def _create_workspace(title="UX Test"):
    resp = client.post("/api/v1/workspaces/", json={
        "title": title,
        "question_id": "C",
        "problem_type": "optimization",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ============================================================
# UX-4: Competition Config
# ============================================================

class TestCompetitionConfig:

    def test_get_default_config(self):
        ws_id = _create_workspace()
        resp = client.get(f"/api/v1/workspaces/{ws_id}/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["competition_type"] == "国赛"
        assert data["language"] == "zh"
        assert data["auto_compile"] is True

    def test_update_config(self):
        ws_id = _create_workspace()
        resp = client.put(
            f"/api/v1/workspaces/{ws_id}/config",
            json={"competition_type": "美赛", "team_name": "Alpha", "language": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competition_type"] == "美赛"
        assert data["team_name"] == "Alpha"
        assert data["language"] == "en"
        # Unchanged fields should persist
        assert data["auto_compile"] is True

    def test_config_persists_across_reads(self):
        ws_id = _create_workspace()
        client.put(
            f"/api/v1/workspaces/{ws_id}/config",
            json={"deadline": "2026-09-15T22:00:00", "review_rounds": 5},
        )
        resp = client.get(f"/api/v1/workspaces/{ws_id}/config")
        data = resp.json()
        assert data["deadline"] == "2026-09-15T22:00:00"
        assert data["review_rounds"] == 5


# ============================================================
# UX-5: Workspace Template
# ============================================================

class TestWorkspaceTemplate:

    def test_standard_dirs_created(self):
        from pathlib import Path
        ws_id = _create_workspace("Template Test")
        ws_path = Path("data") / ws_id
        assert (ws_path / "data").is_dir()
        assert (ws_path / "src").is_dir()
        assert (ws_path / "paper").is_dir()
        assert (ws_path / "output" / "figures").is_dir()
        assert (ws_path / "docs").is_dir()
        assert (ws_path / "config.json").is_file()


# ============================================================
# UX-2 / UX-3: Download & Preview
# ============================================================

class TestDownloadPreview:

    def test_download_pdf_not_found(self):
        ws_id = _create_workspace()
        resp = client.get(f"/api/v1/workspaces/{ws_id}/download/pdf")
        assert resp.status_code == 404

    def test_preview_pdf_not_found(self):
        ws_id = _create_workspace()
        resp = client.get(f"/api/v1/workspaces/{ws_id}/preview/pdf")
        assert resp.status_code == 404

    def test_download_zip(self):
        ws_id = _create_workspace("ZIP Test")
        # Save a test file first
        client.put(
            f"/api/v1/editor/files/{ws_id}/test.txt",
            json={"content": "hello world"},
        )
        resp = client.get(f"/api/v1/workspaces/{ws_id}/download/zip")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert len(resp.content) > 100  # Non-empty ZIP


# ============================================================
# UX-7: Diff
# ============================================================

class TestDiff:

    def test_diff_no_backup(self):
        ws_id = _create_workspace()
        # Save a file
        client.put(
            f"/api/v1/editor/files/{ws_id}/paper/main.tex",
            json={"content": "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"},
        )
        # Diff should show "no changes" since there is no .bak
        resp = client.get(f"/api/v1/editor/diff/{ws_id}/paper/main.tex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_changes"] is False

    def test_diff_with_backup(self):
        ws_id = _create_workspace()
        from pathlib import Path
        # Create file and backup
        ws_path = Path("data") / ws_id / "paper"
        ws_path.mkdir(parents=True, exist_ok=True)
        (ws_path / "main.tex").write_text("old content", encoding="utf-8")
        (ws_path / "main.tex.bak").write_text("new content that is different", encoding="utf-8")
        resp = client.get(f"/api/v1/editor/diff/{ws_id}/paper/main.tex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_changes"] is True


# ============================================================
# UX-8: Pipeline stages list updated
# ============================================================

class TestStagesUpdated:

    def test_stages_include_figure_audit(self):
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()["stages"]]
        assert "figure-audit" in names
        assert "knowledge-archive" in names
        assert "claim-audit" in names

    def test_paper_ref_depends_on_decompose(self):
        resp = client.get("/api/v1/pipeline/stages")
        stages = {s["name"]: s for s in resp.json()["stages"]}
        assert "decompose" in stages["paper-ref"]["depends_on"]


# ============================================================
# UX-1: Resume (basic check that parameter is accepted)
# ============================================================

class TestPipelineResume:

    def test_run_all_endpoint_exists(self):
        """Verify the run-all endpoint accepts start_from parameter."""
        ws_id = _create_workspace("Resume Test")
        # Without problem file, pipeline will skip decompose stages quickly.
        # We just verify the endpoint doesn't 422 on the start_from param.
        resp = client.post(
            f"/api/v1/pipeline/run-all?workspace_id={ws_id}&stages=audit&start_from=audit"
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
