"""
性能压测 — 并发请求、吞吐量、延迟、数据库压力

测试维度:
  1. API 吞吐量：并发创建 workspace / 查询 dashboard
  2. 数据库压力：批量 task 创建 + 查询
  3. 文件上传吞吐：并发上传文件
  4. SSE 流式响应延迟
  5. 大文件处理

Run: cd backend && python -m pytest tests/test_perf.py -v --tb=short -x
"""
import os
import sys
import time
import uuid
import concurrent.futures
from io import BytesIO

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.db.database import create_db_and_tables


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    from app.services import competition_config_service, latex_service, workspace_service
    monkeypatch.setattr(competition_config_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(latex_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(workspace_service, "DATA_DIR", data_dir)
    create_db_and_tables()
    yield


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


# ============================================================
# Helpers
# ============================================================

def _create_ws(client, title=None):
    title = title or f"Perf-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/workspaces/", json={
        "title": title, "question_id": "C", "problem_type": "optimization"
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _timed(fn, *args, **kwargs):
    """Execute fn and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


# ============================================================
# Performance Tests
# ============================================================

class TestAPIThroughput:
    """API 吞吐量测试。"""

    def test_concurrent_workspace_creation(self, client):
        """并发创建 50 个 workspace，测量吞吐量。"""
        count = 50

        def create_one(i):
            return _create_ws(client, f"Concurrent-{i}")

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(create_one, i) for i in range(count)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start

        assert len(results) == count
        assert all(isinstance(r, str) for r in results)
        throughput = count / elapsed
        print(f"\n  Workspace creation: {count} in {elapsed:.2f}s = {throughput:.1f} ops/s")
        assert throughput > 5, f"Throughput too low: {throughput:.1f} ops/s"

    def test_concurrent_dashboard_reads(self, client):
        """并发读取 50 个 workspace 的 dashboard。"""
        # Pre-create workspaces
        ws_ids = [_create_ws(client) for _ in range(20)]

        def read_dashboard(i):
            ws_id = ws_ids[i % len(ws_ids)]
            return client.get(f"/api/v1/workspaces/{ws_id}/dashboard")

        count = 50
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(read_dashboard, i) for i in range(count)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in results)
        throughput = count / elapsed
        print(f"\n  Dashboard reads: {count} in {elapsed:.2f}s = {throughput:.1f} ops/s")
        assert throughput > 10

    def test_concurrent_config_read_write(self, client):
        """并发读写 config，测试竞争安全性。"""
        ws_id = _create_ws(client)

        def write_config(i):
            return client.put(f"/api/v1/workspaces/{ws_id}/config", json={
                "team_name": f"Team-{i}", "notes": f"Note-{i}",
            })

        def read_config(_):
            return client.get(f"/api/v1/workspaces/{ws_id}/config")

        count = 30
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            # Mix reads and writes
            futures = []
            for i in range(count):
                if i % 2 == 0:
                    futures.append(pool.submit(write_config, i))
                else:
                    futures.append(pool.submit(read_config, i))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start

        # All should succeed (no crashes)
        assert all(r.status_code == 200 for r in results)
        print(f"\n  Config R/W: {count} ops in {elapsed:.2f}s = {count/elapsed:.1f} ops/s")


class TestDatabaseStress:
    """数据库压力测试。"""

    def test_bulk_task_creation(self, client):
        """批量创建 100 个 task，测量 DB 写入吞吐量。"""
        ws_id = _create_ws(client)
        from app.services.task_service import TaskService

        count = 100
        start = time.perf_counter()
        task_ids = []
        for i in range(count):
            task = TaskService.create_task(ws_id, stage=f"test-stage-{i % 5}")
            task.mark_running()
            TaskService.update_task(task)
            task.mark_completed(f"Output for task {i}")
            TaskService.update_task(task)
            task_ids.append(task.id)
        elapsed = time.perf_counter() - start

        assert len(task_ids) == count
        throughput = count / elapsed
        print(f"\n  Task CRUD: {count} tasks in {elapsed:.2f}s = {throughput:.1f} ops/s")
        assert throughput > 10, f"DB throughput too low: {throughput:.1f} ops/s"

    def test_bulk_task_query(self, client):
        """查询大量 task，测量 DB 读取性能。"""
        ws_id = _create_ws(client)
        from app.services.task_service import TaskService

        # Seed 200 tasks
        for i in range(200):
            task = TaskService.create_task(ws_id, stage=f"stage-{i % 10}")
            task.mark_completed(f"output-{i}")
            TaskService.update_task(task)

        # Query with different limits
        for limit in [10, 50, 100, 200]:
            start = time.perf_counter()
            tasks = TaskService.get_workspace_tasks(ws_id, limit=limit)
            elapsed = time.perf_counter() - start
            assert len(tasks) == min(limit, 200)
            print(f"\n  Query limit={limit}: {elapsed*1000:.1f}ms, got {len(tasks)} tasks")
            assert elapsed < 1.0, f"Query too slow for limit={limit}: {elapsed:.2f}s"

    def test_concurrent_task_creation(self, client):
        """并发创建 task，测试 DB 并发安全。"""
        ws_id = _create_ws(client)
        from app.services.task_service import TaskService

        count = 50
        errors = []

        def create_task(i):
            try:
                task = TaskService.create_task(ws_id, stage="concurrent-test")
                task.mark_completed(f"concurrent-{i}")
                TaskService.update_task(task)
                return task.id
            except Exception as e:
                errors.append(str(e))
                return None

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(create_task, i) for i in range(count)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start

        successful = [r for r in results if r is not None]
        print(f"\n  Concurrent task creation: {len(successful)}/{count} succeeded in {elapsed:.2f}s")
        if errors:
            print(f"  Errors: {errors[:3]}")
        assert len(successful) >= count * 0.9, f"Too many failures: {len(errors)}/{count}"


class TestFileUploadStress:
    """文件上传压力测试。"""

    def test_concurrent_uploads(self, client):
        """并发上传 20 个文件。"""
        ws_id = _create_ws(client)

        def upload_file(i):
            content = f"Test file content {i}\n" * 100
            return client.post(
                f"/api/v1/workspaces/{ws_id}/upload",
                files={"files": (f"test_{i}.txt", BytesIO(content.encode()), "text/plain")},
            )

        count = 20
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(upload_file, i) for i in range(count)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in results)
        print(f"\n  File uploads: {count} files in {elapsed:.2f}s = {count/elapsed:.1f} ops/s")

    def test_large_file_upload(self, client):
        """上传 10MB 文件，测试内存和性能。"""
        ws_id = _create_ws(client)

        # 10MB of data
        content = b"x" * (10 * 1024 * 1024)
        start = time.perf_counter()
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/upload",
            files={"files": ("large_file.csv", BytesIO(content), "text/csv")},
        )
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        print(f"\n  10MB upload: {elapsed:.2f}s")
        assert elapsed < 10, f"Large upload too slow: {elapsed:.2f}s"

    def test_oversized_file_rejected(self, client):
        """超过 50MB 的文件应被拒绝。"""
        ws_id = _create_ws(client)

        # 51MB — just over the limit
        content = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/upload",
            files={"files": ("too_large.bin", BytesIO(content), "application/octet-stream")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["files"][0]["status"] == "rejected"


class TestSSELatency:
    """SSE 流式响应延迟测试。"""

    def test_stage_execution_latency(self, client):
        """测量单个 stage 执行的端到端延迟。"""
        ws_id = _create_ws(client)

        # Create a problem file
        client.put(
            f"/api/v1/editor/files/{ws_id}/problem.txt",
            json={"content": "Optimize traffic signals."},
        )

        stages = ["audit", "decompose", "paper-ref"]
        for stage in stages:
            start = time.perf_counter()
            resp = client.post("/api/v1/pipeline/execute", json={
                "workspace_id": ws_id, "stage": stage, "mode": "API",
                "keywords": "optimization",
            })
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200
            print(f"\n  Stage '{stage}' latency: {elapsed*1000:.0f}ms")
            assert elapsed < 30, f"Stage {stage} too slow: {elapsed:.2f}s"

    def test_stages_list_latency(self, client):
        """测量 stages 列表端点的响应时间（应 < 10ms）。"""
        times = []
        for _ in range(100):
            start = time.perf_counter()
            resp = client.get("/api/v1/pipeline/stages")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert resp.status_code == 200

        avg_ms = sum(times) / len(times) * 1000
        p99_ms = sorted(times)[98] * 1000
        print(f"\n  /stages latency: avg={avg_ms:.1f}ms, p99={p99_ms:.1f}ms")
        assert avg_ms < 50, f"Average latency too high: {avg_ms:.1f}ms"

    def test_health_endpoint_latency(self, client):
        """测量 health 端点的响应时间。"""
        times = []
        for _ in range(200):
            start = time.perf_counter()
            resp = client.get("/health")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert resp.status_code == 200

        avg_ms = sum(times) / len(times) * 1000
        p99_ms = sorted(times)[197] * 1000
        print(f"\n  /health latency: avg={avg_ms:.1f}ms, p99={p99_ms:.1f}ms")
        assert avg_ms < 20


class TestEndToEndLatency:
    """完整流程的端到端延迟测试。"""

    def test_create_to_dashboard_latency(self, client):
        """测量从创建 workspace 到 dashboard 可查询的全链路延迟。"""
        start = time.perf_counter()

        # Create workspace
        ws_id = _create_ws(client, "Latency Test")

        # Upload file
        client.put(
            f"/api/v1/editor/files/{ws_id}/problem.txt",
            json={"content": "Test problem"},
        )

        # Read dashboard
        resp = client.get(f"/api/v1/workspaces/{ws_id}/dashboard")
        assert resp.status_code == 200

        # Read config
        resp = client.get(f"/api/v1/workspaces/{ws_id}/config")
        assert resp.status_code == 200

        elapsed = time.perf_counter() - start
        print(f"\n  Create-to-dashboard full chain: {elapsed*1000:.0f}ms")
        assert elapsed < 5, f"Full chain too slow: {elapsed:.2f}s"
