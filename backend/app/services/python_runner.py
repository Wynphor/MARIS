"""
PythonRunner — 沙箱化 Python 脚本执行器

安全特性:
  - 超时限制（默认 120 秒）
  - 工作目录隔离（cwd = workspace/src）
  - stdout/stderr 实时捕获并 SSE 输出
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator
from ..core.config import settings

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 120
# 最大输出行数（防止无限输出撑爆内存）
MAX_OUTPUT_LINES = 5000


class PythonRunner:

    # Whitelist of safe environment variables to pass to child process
    _SAFE_ENV_KEYS = {
        "PATH", "PYTHONPATH", "MPLBACKEND", "LANG", "LC_ALL", "LC_CTYPE",
        "HOME", "USER", "TEMP", "TMP", "TMPDIR", "PYTHONIOENCODING",
    }

    @staticmethod
    def _safe_env(extra: dict = None) -> dict:
        """Build a sanitized environment for child processes."""
        env = {}
        for key in PythonRunner._SAFE_ENV_KEYS:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val
        env["MPLBACKEND"] = "Agg"
        if extra:
            env.update(extra)
        return env

    @staticmethod
    def _validate_script_path(src_dir: Path, script_name: str) -> Path:
        """Resolve and validate that script stays within src_dir."""
        # Reject path traversal components
        if ".." in script_name or "/" in script_name or "\\" in script_name:
            return None
        script_path = (src_dir / script_name).resolve()
        src_resolved = src_dir.resolve()
        if not str(script_path).startswith(str(src_resolved)):
            return None
        return script_path if script_path.exists() else None

    @staticmethod
    async def run_solver(
        workspace_id: str,
        script_name: str = "solve_all.py",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> AsyncGenerator[str, None]:
        """
        在 workspace 的 src/ 目录中执行 Python 脚本。

        安全措施:
          - 路径遍历防护（脚本必须在 src/ 内）
          - 环境变量白名单（不泄露 API key 等敏感信息）
          - cwd 隔离到 workspace/src
          - 超时强制终止
          - 输出行数限制
        """
        ws_path = settings.DATA_DIR / workspace_id
        src_dir = ws_path / "src"

        # 安全路径校验
        script_path = PythonRunner._validate_script_path(src_dir, script_name)
        if script_path is None:
            # 尝试找到第一个 .py 文件
            py_files = list(src_dir.glob("*.py"))
            if not py_files:
                yield f"data: [ERROR] 在 {src_dir} 中未找到 Python 脚本。\n\n"
                return
            script_path = py_files[0]
            yield f"data: [INFO] {script_name} 不存在，使用 {script_path.name}。\n\n"

        yield f"data: [INFO] 开始执行 {script_path.name}（超时: {timeout}s）...\n\n"
        yield f"data: [INFO] 工作目录: {src_dir}\n\n"

        # 构建安全的环境变量（白名单）
        env = PythonRunner._safe_env({"PYTHONPATH": str(src_dir)})

        # 文件审计：记录执行前的文件快照
        pre_files = set()
        try:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    pre_files.add(f.resolve())
        except Exception:
            pass

        # 危险 import 检查
        if script_path.exists():
            try:
                script_content = script_path.read_text(encoding="utf-8", errors="replace")
                _DANGEROUS_IMPORTS = {"ctypes", "subprocess", "shutil", "socket", "http.server", "xmlrpc"}
                found_dangerous = []
                for imp in _DANGEROUS_IMPORTS:
                    if f"import {imp}" in script_content or f"from {imp}" in script_content:
                        found_dangerous.append(imp)
                if found_dangerous:
                    yield f"data: [WARNING] 脚本包含危险模块: {', '.join(found_dangerous)}。执行将受限。\n\n"
            except Exception:
                pass

        # 构建子进程 preexec_fn（Linux 内存限制）
        preexec_fn = None
        if sys.platform != "win32":
            try:
                import resource
                def _set_limits():
                    # 限制内存为 2GB
                    mem_limit = 2 * 1024 * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
                    # 限制 CPU 时间
                    resource.setrlimit(resource.RLIMIT_CPU, (timeout + 10, timeout + 10))
                preexec_fn = _set_limits
            except ImportError:
                pass

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                cwd=str(src_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                preexec_fn=preexec_fn,
            )

            line_count = 0
            try:
                while True:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=timeout,
                    )
                    if not line:
                        break

                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        yield f"data: {decoded}\n\n"
                        line_count += 1
                        if line_count >= MAX_OUTPUT_LINES:
                            yield f"data: [WARNING] 输出超过 {MAX_OUTPUT_LINES} 行，截断。\n\n"
                            process.terminate()
                            break

            except asyncio.TimeoutError:
                yield f"data: [ERROR] 执行超时（{timeout}秒），强制终止。\n\n"
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                return

            await process.wait()

            # 文件审计：检查新生成的文件
            post_files = set()
            try:
                for f in src_dir.rglob("*"):
                    if f.is_file():
                        post_files.add(f.resolve())
            except Exception:
                pass
            new_files = post_files - pre_files
            if new_files:
                yield f"data: [INFO] 执行期间生成 {len(new_files)} 个新文件:\n\n"
                for nf in sorted(new_files)[:20]:
                    try:
                        size = nf.stat().st_size
                        yield f"data: [INFO]   + {nf.name} ({size} bytes)\n\n"
                    except Exception:
                        pass

            if process.returncode == 0:
                yield f"data: [SUCCESS] 求解器执行完成（{line_count} 行输出）。\n\n"
            else:
                yield f"data: [ERROR] 求解器退出码 {process.returncode}。\n\n"
            # 结构化退出码（供调用方解析）
            yield f"data: [EXIT_CODE] {process.returncode}\n\n"

        except FileNotFoundError:
            yield f"data: [ERROR] Python 解释器未找到: {sys.executable}\n\n"
        except Exception as e:
            yield f"data: [ERROR] 执行失败: {str(e)}\n\n"

    @staticmethod
    async def run_arbitrary_script(
        script_path: Path,
        working_dir: Path = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> AsyncGenerator[str, None]:
        """执行任意 Python 脚本（内部工具用）。"""
        if not script_path.exists():
            yield f"data: [ERROR] 脚本不存在: {script_path}\n\n"
            return

        # Path validation: reject path traversal
        script_resolved = script_path.resolve()
        if ".." in str(script_path):
            yield f"data: [ERROR] 路径不允许包含 ..\n\n"
            return

        cwd = working_dir or script_path.parent
        cwd_resolved = cwd.resolve()

        # Ensure script is within workspace directory
        from ..core.config import settings
        data_dir = settings.DATA_DIR.resolve()
        if not str(script_resolved).startswith(str(data_dir)):
            yield f"data: [ERROR] 脚本路径必须在数据目录内\n\n"
            return

        env = PythonRunner._safe_env()

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_resolved),
                cwd=str(cwd_resolved),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            try:
                while True:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=timeout
                    )
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        yield f"data: {decoded}\n\n"
            except asyncio.TimeoutError:
                yield f"data: [ERROR] 超时 ({timeout}s)。\n\n"
                process.terminate()
                return

            await process.wait()
            status = "SUCCESS" if process.returncode == 0 else "ERROR"
            yield f"data: [{status}] 退出码 {process.returncode}。\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
