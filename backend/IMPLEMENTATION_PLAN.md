# MathModel-Engine 后端开发计划

## 目标
将 FastAPI 后端从骨架（大量 stub/mock）升级为可真实运行的完整后端，
接入 MiMo、DeepSeek、Gemini 三个 LLM Provider，让 Pipeline 全链路可用。

## Provider 策略
- **MiMo** (OpenAI 兼容): 模型路由按 `mimo_client.py` 的 TASK_MODEL 映射
- **DeepSeek** (OpenAI 兼容): 主力推理模型
- **Gemini**: 优先 API Key (google-generativeai SDK)，无 Key 时回退 CLI
- 所有调用必须支持 **SSE 流式输出**

---

## Phase 1: 核心 AI 基础设施（P0，阻塞级）

### Task 1.1 — 创建 Prompt 模板系统
- 文件: `backend/app/core/prompts.py`
- 迁移 `src/mimo_client.py` 的 SYSTEM_PROMPTS 到此
- 为每个 pipeline stage 定义 prompt 构建函数:
  - `build_decompose_prompt(ws_id, problem_text)`
  - `build_model_select_prompt(ws_id)`
  - `build_code_gen_prompt(ws_id, question)`
  - `build_write_prompt(ws_id)` — 注入 paper-write-override + RAG context
  - `build_review_prompt(ws_id, stage)` — Red/Blue team 对抗 prompt
  - `build_format_check_prompt(ws_id)`
  - `build_claim_audit_prompt(ws_id)`

### Task 1.2 — 实现 APIClientService 真实调用
- 文件: `backend/app/services/api_client_service.py`
- 用 `httpx.AsyncClient` 实现流式 SSE 调用
- OpenAI 兼容接口（DeepSeek + MIMO）:
  - POST `{base_url}/chat/completions` + `stream: true`
  - 解析 SSE 的 `data: {...}` 逐 chunk yield
  - 提取 `choices[0].delta.content`
- Gemini:
  - 有 API Key → `google-generativeai` SDK 的 `generate_content(stream=True)`
  - 无 API Key → 回退 CLI (`gemini --skip-trust -p`)
- 统计信息 yield: model, tokens, cache_hit 等
- 错误处理: API Key 缺失、超时、rate limit、网络错误

### Task 1.3 — 升级 AIService 集成真实调用
- 文件: `backend/app/services/ai_service.py`
- `run_task()` 现在委托给 APIClientService 真实调用
- `run_cli_task()` 保留作为 fallback
- 添加 provider 路由逻辑（按 mimo_client.py 的 TASK_MODEL 映射）

---

## Phase 2: 服务层接入真实 LLM（P1）

### Task 2.1 — ReviewService 对抗审查
- 文件: `backend/app/services/review_service.py`
- Red Team: 调 DeepSeek API，system prompt = 审稿人角色
- Blue Team: 调 MiMo/Gemini API，system prompt = 防御者角色
- 支持多轮对话（将 Red 的攻击作为 Blue 的输入上下文）
- 全程 SSE 流式输出

### Task 2.2 — OrchestratorService 自动改进循环
- 文件: `backend/app/services/orchestrator_service.py`
- 真实调用 AI 修复论文/代码（替代 asyncio.sleep mock）
- 循环: compile → review → AI fix → recompile
- 最大轮次可配置，提前终止条件基于 review 评分

### Task 2.3 — Pipeline 路由增强
- 文件: `backend/app/api/routes/pipeline.py`
- 每个 stage 使用 prompts.py 的函数构建完整 prompt
- decompose: 读取赛题文本 → 拆解 prompt → AI 调用 → 写入 problem_decomposition.md
- model-select: 读取 decomposition → 推荐 prompt → AI → 写入 model_recommendation.md
- code-gen: 读取 recommendation → 代码生成 prompt → AI → 写入 src/
- write: 读取 recommendation + override → 论文写作 prompt → AI → 写入 paper/main.tex
- 所有 stage 的 AI 输出通过 SSE 实时推送到前端

---

## Phase 3: 加固与补全（P2/P3）

### Task 3.1 — FastAPI lifespan 迁移
- 文件: `backend/app/main.py`
- 将 `@app.on_event("startup")` 替换为 `lifespan` context manager

### Task 3.2 — PythonRunner 沙箱增强
- 文件: `backend/app/services/python_runner.py`
- 添加超时限制（默认 60s）
- 添加工作目录隔离（cwd = workspace/src）
- 捕获并流式输出 stderr

### Task 3.3 — 集成测试
- 编写基础测试验证:
  - API 路由可访问
  - Workspace CRUD 正常
  - Pipeline execute 返回 SSE 流
  - APIClientService 能真实调通至少一个 provider

---

## 执行顺序
Phase 1 → Phase 2 → Phase 3，每 Phase 完成后自动审查代码 → 修 bug → 进入下一 Phase。

## 预计文件变更
- 新建: `backend/app/core/prompts.py`
- 重写: `backend/app/services/api_client_service.py`
- 修改: `backend/app/services/ai_service.py`
- 修改: `backend/app/services/review_service.py`
- 修改: `backend/app/services/orchestrator_service.py`
- 修改: `backend/app/api/routes/pipeline.py`
- 修改: `backend/app/main.py`
- 修改: `backend/app/services/python_runner.py`
- 新建: `backend/tests/test_api.py`
