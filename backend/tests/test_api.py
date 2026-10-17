"""
集成测试 — 验证后端核心功能

运行: cd backend && python -m pytest tests/ -v
"""
import pytest
import json
import sys
import os

# 确保能导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import create_db_and_tables


@pytest.fixture(scope="module")
def client():
    """创建测试客户端（每个测试模块初始化一次）。"""
    create_db_and_tables()
    with TestClient(app) as c:
        yield c


# ============================================================
# 基础路由测试
# ============================================================

class TestBasicRoutes:
    """测试基础路由是否可访问。"""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "MathModel-Engine" in data["message"]
        assert data["version"] == "2.0.0"

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_stages_list(self, client):
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        stages = resp.json()["stages"]
        stage_names = [s["name"] for s in stages]
        assert "decompose" in stage_names
        assert "model-select" in stage_names
        assert "code-gen" in stage_names
        assert "write" in stage_names
        assert "review" in stage_names
        assert "pack" in stage_names


# ============================================================
# Workspace CRUD 测试
# ============================================================

class TestWorkspaces:
    """测试 Workspace CRUD 操作。"""

    def test_create_workspace(self, client):
        resp = client.post("/api/v1/workspaces/", json={
            "title": "测试工作区",
            "question_id": "C",
            "problem_type": "优化类",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "测试工作区"
        assert data["question_id"] == "C"
        assert data["status"] == "INIT"
        assert "id" in data
        TestWorkspaces._ws_id = data["id"]

    def test_list_workspaces(self, client):
        resp = client.get("/api/v1/workspaces/")
        assert resp.status_code == 200
        ws_list = resp.json()
        assert len(ws_list) >= 1

    def test_get_workspace_tree(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.get(f"/api/v1/workspaces/{ws_id}/tree")
        assert resp.status_code == 200
        tree = resp.json()
        # 应该包含 src, output, paper 子目录
        dir_names = [node["name"] for node in tree]
        assert "src" in dir_names
        assert "paper" in dir_names


# ============================================================
# Editor 测试
# ============================================================

class TestEditor:
    """测试文件读写和编译接口。"""

    def test_save_and_read_file(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")

        # 保存文件
        resp = client.put(
            f"/api/v1/editor/files/{ws_id}/src/test.py",
            json={"content": "print('hello')"},
        )
        assert resp.status_code == 200

        # 读取文件
        resp = client.get(f"/api/v1/editor/files/{ws_id}/src/test.py")
        assert resp.status_code == 200
        assert resp.json()["content"] == "print('hello')"

    def test_path_traversal_blocked(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.get(f"/api/v1/editor/files/{ws_id}/../../../etc/passwd")
        # 403 (安全拦截) 或 404 (路径规范化后不存在) 均可接受，关键是不能返回 200
        assert resp.status_code in (403, 404)


# ============================================================
# Pipeline SSE 测试（不调真实 LLM，测试路由分发）
# ============================================================

class TestPipeline:
    """测试 Pipeline 路由分发。"""

    def test_ingest_stage_no_file(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id,
            "stage": "ingest",
            "keywords": "nonexistent.xlsx",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_audit_stage(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id,
            "stage": "audit",
        })
        assert resp.status_code == 200

    def test_unknown_stage_rejected(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id,
            "stage": "nonexistent_stage",
        })
        assert resp.status_code == 400

    def test_workspace_not_found(self, client):
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": "nonexistent-id",
            "stage": "decompose",
        })
        assert resp.status_code == 404


# ============================================================
# Prompts 系统测试
# ============================================================

class TestPrompts:
    """测试 Prompt 模板系统。"""

    def test_build_decompose_prompt(self):
        from app.core.prompts import build_decompose_prompt
        system, user = build_decompose_prompt("test-ws", "某工厂生产两种产品...")
        assert "拆解" in system or "子问题" in system
        assert "test-ws" in user
        assert "某工厂" in user

    def test_build_model_select_prompt(self):
        from app.core.prompts import build_model_select_prompt
        system, user = build_model_select_prompt("test-ws", "## 子问题1...")
        assert "模型" in system
        assert "test-ws" in user

    def test_build_review_prompt_red(self):
        from app.core.prompts import build_review_prompt
        system, user = build_review_prompt("test-ws", "\\documentclass...", role="red")
        assert "审稿" in system or "Red Team" in system

    def test_build_review_prompt_blue(self):
        from app.core.prompts import build_review_prompt
        system, user = build_review_prompt("test-ws", "\\documentclass...", role="blue")
        assert "回应" in system or "Blue Team" in system or "修改" in system

    def test_get_model_for_stage(self):
        from app.core.prompts import get_model_for_stage
        assert get_model_for_stage("decompose")["provider"] == "deepseek"
        assert get_model_for_stage("red-team")["provider"] == "deepseek"
        assert get_model_for_stage("blue-team")["provider"] == "mimo"

    def test_paper_write_override_present(self):
        from app.core.prompts import PAPER_WRITE_OVERRIDE
        assert "三线表" in PAPER_WRITE_OVERRIDE
        assert "此处省略" in PAPER_WRITE_OVERRIDE  # 应该是禁令中提到的


# ============================================================
# APIClientService 配置测试
# ============================================================

class TestAPIClientService:
    """测试 APIClientService 配置完整性。"""

    def test_provider_configs_exist(self):
        from app.services.api_client_service import PROVIDER_CONFIGS
        assert "deepseek" in PROVIDER_CONFIGS
        assert "mimo" in PROVIDER_CONFIGS
        assert "gemini" in PROVIDER_CONFIGS
        assert "claude" in PROVIDER_CONFIGS

    def test_provider_types(self):
        from app.services.api_client_service import PROVIDER_CONFIGS
        assert PROVIDER_CONFIGS["deepseek"]["type"] == "openai_compat"
        assert PROVIDER_CONFIGS["claude"]["type"] == "anthropic"
        assert PROVIDER_CONFIGS["gemini"]["type"] == "gemini"


# ============================================================
# 文件上传测试
# ============================================================

class TestFileUpload:
    """测试文件上传功能。"""

    def test_upload_text_file(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")

        # 创建临时文件
        import io
        file_content = b"Test problem statement content"
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/upload",
            files=[("files", ("problem.txt", file_content, "text/plain"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["uploaded"] == 1
        assert data["files"][0]["status"] == "uploaded"

    def test_upload_rejects_unsupported_type(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/upload",
            files=[("files", ("malware.exe", b"MZ...", "application/octet-stream"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["files"][0]["status"] == "rejected"

    def test_list_uploaded_files(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.get(f"/api/v1/workspaces/{ws_id}/files")
        assert resp.status_code == 200
        assert "files" in resp.json()


# ============================================================
# 任务查询测试
# ============================================================

class TestTasks:
    """测试任务持久化和查询。"""

    def test_tasks_list_empty(self, client):
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.get(f"/api/v1/tasks/workspace/{ws_id}")
        assert resp.status_code == 200

    def test_task_not_found(self, client):
        resp = client.get("/api/v1/tasks/nonexistent-task-id")
        assert resp.status_code == 404


# ============================================================
# Stage Machine 测试
# ============================================================

class TestStageMachine:
    """测试 Stage 依赖检查和审批机制。"""

    def test_approve_and_reject(self, client):
        """测试审批/拒绝接口可正常访问。"""
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        # 前面的测试可能已创建了 completed task，所以 200 或 422 都合理
        resp = client.post(f"/api/v1/pipeline/{ws_id}/approve")
        assert resp.status_code in (200, 422)

        resp = client.post(f"/api/v1/pipeline/{ws_id}/reject?feedback=test feedback")
        assert resp.status_code in (200, 422)

    def test_stage_dependency_blocks_unmet(self, client):
        """model-select 依赖 decompose，未执行 decompose 时应被阻止。"""
        ws_id = getattr(TestWorkspaces, "_ws_id", None)
        if not ws_id:
            pytest.skip("No workspace created")
        resp = client.post("/api/v1/pipeline/execute", json={
            "workspace_id": ws_id,
            "stage": "model-select",
        })
        # 应返回 422（前置依赖未满足）
        assert resp.status_code == 422
        assert "decompose" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
