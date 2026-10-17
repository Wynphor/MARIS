import asyncio
import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
from enum import Enum
from ..core.config import settings

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"

class SimulationJob:
    def __init__(self, workspace_id: str, val_type: str, script_path: Path):
        self.id = str(uuid.uuid4())[:8]
        self.workspace_id = workspace_id
        self.val_type = val_type
        self.script_path = script_path
        self.status = JobStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.output_log: List[str] = []
        self.exit_code: Optional[int] = None

class SimulationQueue:
    def __init__(self, max_parallel: int = 2):
        self.max_parallel = max_parallel
        self.jobs: Dict[str, SimulationJob] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start_worker(self):
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        semaphore = asyncio.Semaphore(self.max_parallel)
        while True:
            job: SimulationJob = await self.queue.get()
            asyncio.create_task(self._run_job_with_semaphore(job, semaphore))
            self.queue.task_done()

    async def _run_job_with_semaphore(self, job: SimulationJob, semaphore: asyncio.Semaphore):
        async with semaphore:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            try:
                # CWD 设为 workspace 根目录（不是 src/），确保 output/tables/ 和 output/figures/ 解析正确
                ws_dir = str(settings.DATA_DIR / job.workspace_id)
                process = await asyncio.create_subprocess_exec(
                    sys.executable, str(job.script_path),
                    cwd=ws_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                
                while True:
                    line = await process.stdout.readline()
                    if not line: break
                    msg = line.decode('utf-8', errors='replace').strip()
                    job.output_log.append(msg)
                
                job.exit_code = await process.wait()
                job.status = JobStatus.COMPLETED if job.exit_code == 0 else JobStatus.FAILED
            except Exception as e:
                job.status = JobStatus.FAILED
                job.output_log.append(f"Internal Error: {str(e)}")
            
            job.finished_at = datetime.now()

# Singleton Queue Instance
global_sim_queue = SimulationQueue()

class SimulationService:
    @staticmethod
    async def run_validation(workspace_id: str, val_type: str) -> AsyncGenerator[str, None]:
        """
        7.10 Simulation Queue & State Machine (ARIS-inspired)
        Queues the validation task and streams the live status.
        """
        ws_path = settings.DATA_DIR / workspace_id
        src_dir = ws_path / "src"
        
        scripts = {
            "sensitivity": "sensitivity_analysis.py",
            "stability": "seed_sweep_audit.py",
            "monte_carlo": "mc_simulation.py"
        }
        
        script_name = scripts.get(val_type, "validate.py")
        script_path = src_dir / script_name
        
        if not script_path.exists():
            # Auto-generate the script via LLM
            yield f"data: [INFO] {script_name} 不存在，AI 自动生成中...\n\n"
            try:
                gen_success = await SimulationService._generate_validation_script(
                    workspace_id, val_type, script_name, src_dir
                )
                if gen_success:
                    yield f"data: [SUCCESS] 已自动生成 {script_name}\n\n"
                else:
                    yield f"data: [ERROR] 自动生成 {script_name} 失败。\n\n"
                    return
            except Exception as e:
                yield f"data: [ERROR] 自动生成失败: {str(e)}\n\n"
                return

        # Initialize and Queue Job
        job = SimulationJob(workspace_id, val_type, script_path)
        global_sim_queue.jobs[job.id] = job
        await global_sim_queue.queue.put(job)
        global_sim_queue.start_worker()

        yield f"data: [INFO] Job {job.id} queued in position {global_sim_queue.queue.qsize()}...\n\n"
        
        # Stream Wait Loop
        last_log_idx = 0
        while job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            if last_log_idx < len(job.output_log):
                for i in range(last_log_idx, len(job.output_log)):
                    yield f"data: [{job.id}] {job.output_log[i]}\n\n"
                last_log_idx = len(job.output_log)
            await asyncio.sleep(0.5)

        # Final logs
        for i in range(last_log_idx, len(job.output_log)):
            yield f"data: [{job.id}] {job.output_log[i]}\n\n"
            
        yield f"data: [FINISH] Job {job.id} ended with status: {job.status}\n\n"
        yield f"data: {json.dumps({'job_id': job.id, 'status': job.status, 'exit_code': job.exit_code})}\n\n"

    @staticmethod
    async def _generate_validation_script(
        workspace_id: str, val_type: str, script_name: str, src_dir: Path
    ) -> bool:
        """
        使用 LLM 自动生成验证/敏感性分析脚本。
        读取 solve_all.py 和 model_recommendation.md 作为上下文。
        """
        from ..core.prompts import read_workspace_file
        from .api_client_service import APIClientService

        # Read context files
        solve_code = read_workspace_file(workspace_id, "src/solve_all.py") or ""
        model_rec = read_workspace_file(workspace_id, "model_recommendation.md") or ""
        decomp = read_workspace_file(workspace_id, "problem_decomposition.md") or ""

        # Truncate if too long
        if len(solve_code) > 6000:
            solve_code = solve_code[:6000] + "\n# ... (truncated)"
        if len(model_rec) > 2000:
            model_rec = model_rec[:2000]

        type_descriptions = {
            "sensitivity": (
                "敏感性分析脚本。要求：\n"
                "1. 对模型关键参数做 ±10%, ±20%, ±30% 扰动\n"
                "2. 记录每个参数扰动下的结果变化（输出 CSV）\n"
                "3. 生成参数-结果灵敏度条形图（保存到 output/figures/）\n"
                "4. 输出结果到 output/tables/sensitivity_results.csv\n"
                "5. 含 if __name__ == '__main__' 入口\n"
                "6. 可直接 python 运行\n"
            ),
            "stability": (
                "稳定性检验脚本（随机种子扫描）。要求：\n"
                "1. 用 10+ 个不同随机种子运行模型\n"
                "2. 记录每次结果的均值和标准差\n"
                "3. 判断结果稳定性（CV < 5% 为稳定）\n"
                "4. 输出到 output/tables/stability_results.csv\n"
                "5. 含 if __name__ == '__main__' 入口\n"
            ),
            "monte_carlo": (
                "蒙特卡洛模拟脚本。要求：\n"
                "1. 对不确定参数做 1000+ 次随机抽样\n"
                "2. 运行模型得到结果分布\n"
                "3. 计算置信区间和风险概率\n"
                "4. 输出分布直方图到 output/figures/\n"
                "5. 含 if __name__ == '__main__' 入口\n"
            ),
        }

        desc = type_descriptions.get(val_type, "验证分析脚本。")

        system_prompt = (
            f"你是数学建模验证分析专家。根据已有的求解代码和模型推荐，生成{desc}\n"
            f"输出完整 Python 代码，使用 artifact 协议：\n"
            f"<artifact path=\"src/{script_name}\">完整 Python 代码</artifact>\n"
            "注意：代码必须可直接运行，依赖只能用 numpy/pandas/matplotlib/scipy。"
        )

        user_prompt = (
            f"## 模型推荐\n{model_rec}\n\n"
            f"## 现有求解代码\n```python\n{solve_code}\n```\n\n"
            f"请基于以上信息，生成 {script_name}。"
        )

        # Call LLM
        collected = ""
        async for chunk in APIClientService.call_llm(
            system=system_prompt, user=user_prompt, temperature=0.3,
        ):
            collected += chunk

        # Extract and save the script
        from .output_persistence_service import OutputPersistenceService
        import re
        # Try artifact protocol first
        artifact_match = re.search(
            rf'<artifact\s+path=["\']src/{re.escape(script_name)}["\']\s*>(.*?)</artifact>',
            collected, re.DOTALL | re.IGNORECASE,
        )
        if artifact_match:
            code = artifact_match.group(1).strip()
        else:
            # Try code block
            code_match = re.search(r"```python\s*\n(.*?)```", collected, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            else:
                return False

        if not code or len(code) < 100:
            return False

        src_dir.mkdir(parents=True, exist_ok=True)
        script_path = src_dir / script_name
        script_path.write_text(code, encoding="utf-8")
        return True

