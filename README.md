# MathModel-Engine

数学建模竞赛全流程自动化后端 —— 从赛题上传到论文提交，AI 驱动的端到端解决方案。

MARIS（MathModel-Engine）是一套面向数学建模竞赛的端到端自动化系统，基于 ARIS 框架改造。系统集成 FastAPI 后端与 Vue/Tauri 桌面前端，内置 21 个 Pipeline 阶段，覆盖竞赛全流程：赛题拆解 → 文献调研 → 模型推荐 → 代码生成 → 图表制作 → LaTeX 论文写作与自动编译 → 红蓝对抗审查 → 格式检查 → 提交打包。支持 DeepSeek、MiMo、OpenAI、Claude、Gemini、Grok 六个大模型供应商协同工作，通过多模型分工（深度推理、轻量执行、交叉审查）平衡效果与成本，并配套完整的竞赛技能库（problem-decompose、model-select、code-template、sensitivity-analysis、contest-format、submit-pack 等）与历届真题、获奖论文参考资料，目标是在 3 天赛程内将"读题到定稿"压缩至数小时，为参赛队伍留足决策与打磨时间。

## 功能特性

- **21 个 Pipeline Stage** 覆盖竞赛全流程：赛题拆解 → 模型推荐 → 代码生成 → 论文写作 → 红蓝对抗审查 → 自动改进 → 格式检查 → 提交打包
- **6 个 LLM Provider** 真实集成：DeepSeek / MiMo / OpenAI / Claude / Gemini / Grok
- **红蓝对抗审查**：Red Team (DeepSeek) 攻击 + Blue Team (MiMo) 防御，可配置轮数
- **一键全流程** `POST /run-all`，支持断点恢复（`start_from` 参数）
- **自动落盘**：AI 输出自动保存到 workspace 文件
- **自动编译**：论文生成后自动 LaTeX 后处理 + xelatex 编译
- **人工审核暂停**：关键阶段支持 approve/reject 人工干预
- **实时 SSE 流式推送**：所有 AI 阶段实时输出

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone <repo-url>
cd shuxuejianmo

# 安装依赖
cd backend
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入至少一个 LLM Provider 的 API Key
# 最低要求: DEEPSEEK_API_KEY
```

### 3. 启动

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

### 4. Docker 启动（可选）

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
docker-compose up -d
```

## API 文档速查

### 基础

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息 |
| GET | `/health` | 健康检查 |

### Workspace 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/workspaces/` | 创建工作区 |
| GET | `/api/v1/workspaces/` | 列表 |
| GET | `/api/v1/workspaces/{id}/tree` | 文件树 |
| GET | `/api/v1/workspaces/{id}/dashboard` | 仪表盘 |
| POST | `/api/v1/workspaces/{id}/upload` | 文件上传 |
| GET | `/api/v1/workspaces/{id}/files` | 已上传文件列表 |
| GET/PUT | `/api/v1/workspaces/{id}/config` | 竞赛配置 |
| GET | `/api/v1/workspaces/{id}/download/pdf` | 下载论文 PDF |
| GET | `/api/v1/workspaces/{id}/preview/pdf` | 浏览器预览 PDF |
| GET | `/api/v1/workspaces/{id}/download/zip` | 下载 ZIP 包 |

### Pipeline 执行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/pipeline/execute` | 执行单个 stage |
| POST | `/api/v1/pipeline/run-all` | 一键全流程 |
| POST | `/api/v1/pipeline/{id}/approve` | 人工审批 |
| POST | `/api/v1/pipeline/{id}/reject` | 人工拒绝 |
| GET | `/api/v1/pipeline/stages` | stage 列表 |

### 编辑器

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/editor/files/{id}/{path}` | 读取文件 |
| PUT | `/api/v1/editor/files/{id}/{path}` | 保存文件 |
| GET | `/api/v1/editor/diff/{id}/{path}` | 文件变更对比 |
| POST | `/api/v1/editor/ai-edit/{id}/{path}` | AI 增量修改 |
| POST | `/api/v1/editor/run/{id}` | 执行 Python |
| POST | `/api/v1/editor/compile/{id}` | LaTeX 编译 |

### 任务查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/tasks/{id}` | 任务详情 |
| GET | `/api/v1/tasks/workspace/{id}` | 任务历史 |
| GET | `/api/v1/tasks/workspace/{id}/stage/{s}` | 按 stage 查询 |
| GET | `/api/v1/tasks/{id}/events` | SSE 事件回放 |

## Pipeline Stage

```
ingest → audit → preprocess → decompose → model-select → paper-ref →
code-gen → figure-gen → write(+auto-compile) → compile →
review → format-check → claim-audit → citation-audit →
auto-improve → validate → figures → pack → archive
```

### Stage 依赖关系

| Stage | 依赖 | 说明 |
|-------|------|------|
| decompose | 无 | 赛题拆解 |
| model-select | decompose | 模型推荐 |
| code-gen | model-select | 代码生成 |
| figure-gen | code-gen | 图表生成 |
| write | model-select | 论文写作（自动编译） |
| review | write | 红蓝对抗审查 |
| format-check | write | 格式检查 |
| claim-audit | write | 数值声明审计 |
| citation-audit | write | 引用审计 |
| auto-improve | review | 自动改进循环 |
| compile | write | LaTeX 编译 |
| validate | code-gen | 敏感性分析 |
| figures | code-gen | 图表审计 |
| pack | write, format-check | 提交打包 |
| archive | pack | 知识归档 |

## 项目结构

```
shuxuejianmo/
├── .env.example              # 环境变量模板
├── .github/workflows/test.yml # CI 配置
├── docker-compose.yml         # Docker 编排
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── core/
│   │   │   ├── config.py      # 配置管理
│   │   │   └── prompts.py     # Prompt 模板 + 模型路由
│   │   ├── db/
│   │   │   └── database.py    # 数据库引擎
│   │   ├── models/
│   │   │   ├── workspace.py   # Workspace 模型
│   │   │   └── pipeline.py    # Pipeline 模型
│   │   ├── services/          # 19 个服务模块
│   │   └── api/routes/        # 4 个路由模块
│   └── tests/
│       ├── test_api.py        # API 测试
│       └── test_ux.py         # UX 功能测试
└── data/                      # Workspace 数据目录
```

## 技术栈

- **Python 3.11+** / FastAPI / SQLModel / httpx SSE
- **数据库**: SQLite（开发）/ 可替换为 PostgreSQL
- **LLM**: 6 个 Provider，统一 SSE 流式接口
- **LaTeX**: xelatex 编译 + 自动后处理

## 开发

```bash
# 运行测试
cd backend
python -m pytest tests/ -v

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

## License

MIT
