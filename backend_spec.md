# MathModel-Engine Backend Specification

This document provides a highly detailed architectural blueprint, API schema, and migration plan for transitioning the CLI-based mathematical modeling automation pipeline into a robust FastAPI backend.

## 1. Project Structure

We will enforce the following strict directory structure to ensure separation of concerns:

```text
backend/
├── app/
│   ├── api/                  # API Routers
│   │   ├── dependencies.py   # FastAPI dependencies (auth, workspace context)
│   │   ├── routes/
│   │   │   ├── workspaces.py # Workspace CRUD & file management
│   │   │   ├── pipeline.py   # AI orchestration & pipeline triggers
│   │   │   └── editor.py     # Real-time TeX/Markdown preview & edit
│   ├── core/                 # Core logic and configuration
│   │   ├── config.py         # Pydantic BaseSettings (MIMO_API_KEY, paths)
│   │   ├── prompts.py        # Centralized prompt templates (migrated from skills/)
│   ├── models/               # Pydantic Schemas (The Contract)
│   │   ├── workspace.py
│   │   ├── pipeline.py
│   ├── services/             # Business Logic (The heavy lifters)
│   │   ├── ai_service.py     # Encapsulates Gemini/MiMo calls
│   │   ├── latex_service.py  # Ported from src/pipeline.py (wrap_tables, compile)
│   │   ├── python_runner.py  # Sandboxed execution of generated Python code
│   ├── db/                   # Database (SQLite for simplicity, tracking tasks)
│   └── main.py               # FastAPI application factory
├── data/                     # Root folder for isolated user workspaces
├── requirements.txt
└── .env
```

## 2. Core Pydantic Models (The API Contract)

These schemas ensure strict validation between the Frontend and Backend.

```python
# backend/app/models/workspace.py
from pydantic import BaseModel
from typing import List, Optional

class WorkspaceCreate(BaseModel):
    title: str               # e.g., "2025-C 碳排放优化"
    question_id: str         # e.g., "C"
    problem_type: str        # e.g., "优化类"

class WorkspaceResponse(WorkspaceCreate):
    id: str                  # UUID
    created_at: str
    status: str              # "INIT", "DECOMPOSED", "SOLVED", "FINISHED"

class FileNode(BaseModel):
    name: str
    path: str
    type: str                # "file" or "directory"
    size: Optional[int]
```

```python
# backend/app/models/pipeline.py
from pydantic import BaseModel

class PipelineRequest(BaseModel):
    workspace_id: str
    stage: str               # e.g., "decompose", "model-select", "code-gen"
    # Optional parameters depending on the stage
    data_path: Optional[str] = None
    keywords: Optional[str] = None
```

## 3. Migration Plan: CLI `src/pipeline.py` to `FastAPI Services`

The existing `src/pipeline.py` is procedural. We must refactor it into object-oriented services to prevent blocking the async event loop.

### A. The AI Execution Layer (`services/ai_service.py`)
Previously: `_gemini()` and `_mimo()` functions invoking CLI commands.
**Refactor:**
Instead of `subprocess.run(["gemini", ...])`, we will integrate the AI SDKs directly (or use HTTP calls to the Antigravity engine if we maintain it as a sidecar). This provides native async support.
*   **Crucial:** Must support streaming responses (`StreamingResponse` in FastAPI) so the frontend UI can show typing effects during long prompts (like `paper-write`).

### B. The LaTeX Post-Processor (`services/latex_service.py`)
Previously: `wrap_tables_in_tex()`, `check_placeholders()`, `compile_pdf()` in `pipeline.py`.
**Refactor:**
*   Move these exactly as they are, but make them methods of `LatexService`.
*   **Rule Enforcement:** `LatexService.compile(workspace_id)` MUST always run `wrap_tables_in_tex()` and `check_placeholders()` BEFORE calling `xelatex`.
*   If `check_placeholders()` fails, the API must return a `422 Unprocessable Entity` with the exact placeholder details, forcing the Frontend to show an alert to the user.
*   The double compilation (`pass 1`, `pass 2`) must remain intact to resolve cross-references.

### C. The Python Execution Sandbox (`services/python_runner.py`)
Previously: `stage_solve()` running `subprocess.run([sys.executable, str(py_file)])`.
**Refactor:**
*   This is dangerous in a web server. It must be wrapped with timeouts and memory limits.
*   Output stdout/stderr must be captured in real-time and pushed to the frontend via Server-Sent Events (SSE).

## 4. API Endpoints Specification

### 4.1 Orchestration (The Pipeline)
**`POST /api/v1/pipeline/execute`**
This endpoint replaces the `python pipeline.py --stage X` command.
It accepts a `PipelineRequest` and returns an SSE stream.
**Behavior:**
1. Validates the `workspace_id`.
2. Matches the `stage` to the corresponding service method (e.g., `ai_service.stage_decompose()`).
3. Yields log lines: `yield f"data: [INFO] Starting decomposition...\n\n"`.

### 4.2 File Management
**`GET /api/v1/workspaces/{workspace_id}/tree`**
Returns a recursive JSON structure of the workspace folder (excluding `.git` and `__pycache__`) mapped to the `FileNode` schema.

**`GET /api/v1/workspaces/{workspace_id}/files/{file_path:path}`**
If it's a `.md`, `.py`, or `.tex` file, return text content.
If it's a `.pdf` or `.png`, return the binary stream with appropriate MIME types (`application/pdf`, `image/png`).

## 5. Handling the "Anti-Laziness" Overrides

The rules defined in `skills-mathmodel/paper-write-override.md` MUST be injected systematically.
**Refactor:**
Create a configuration injection pipeline in `core/prompts.py`. Whenever `ai_service.stage_write()` is called, it must automatically append the contents of the override markdown to the system prompt. The backend must enforce that the AI cannot bypass these instructions.

## 6. Deployment Considerations
*   Since `xelatex` and specific Python math libraries (numpy, scipy, pulp) are required, the backend MUST be distributed via a `Dockerfile` that installs `texlive-xetex` and the `requirements.txt`.

## 7. Advanced Workflow Integrations (Next-Generation Features)

The following advanced steps from the manual CLI workflow and `AGENTS.md` roadmap are to be systematically integrated into the backend architecture to achieve a fully automated, end-to-end mathematical modeling pipeline.

### 7.1 Multi-Problem Triage (多赛题初筛与决策)
*   **Missing Link:** The current backend assumes a single problem is already selected. The crucial first hour "triage" phase is manual.
*   **Integration Plan:** 
    *   Add an API route: `POST /api/v1/workspaces/triage`
    *   **Behavior:** Accepts multiple problem PDFs (e.g., C, D, E). Uses `AIService` to concurrently analyze data requirements, required skills (e.g., OpenCV vs. PuLP), and team compatibility. Returns a structured JSON decision matrix comparing the difficulty and recommended choice.

### 7.2 External Data Scraping (外部数据主动采集)
*   **Missing Link:** `DataService` only handles local Excel/CSV conversions. It lacks active data gathering capabilities required for policy/economic problems (like 2025 Problem C).
*   **Integration Plan:**
    *   Enhance `DataService` with a `scrape_external_data` method.
    *   **Behavior:** Integrates with tools like `exa-search` or dedicated web scraping APIs to find and download datasets from sources like the National Bureau of Statistics or World Bank based on problem context.

### 7.3 Real-Time Adversarial Review (实战化的对抗性审查循环)
*   **Missing Link:** `ReviewService` currently only has a placeholder structure without true multi-turn, multi-agent adversarial interaction.
*   **Integration Plan:**
    *   Implement the `auto-review-loop` from `AGENTS.md`.
    *   **Behavior:** Instantiate a Red Team agent (DeepSeek V4 Pro) to critique the modeling/logic, and a Blue Team agent (Gemini/MiMo) to defend or rewrite the code/LaTeX. This runs as a multi-turn SSE stream in the `review` pipeline stage.

### 7.4 Semantic & Claim Audit (数值一致性审计)
*   **Missing Link:** `ComplianceService` only checks for identity leaks (double-blind). It doesn't verify if the paper's claims match the code's output.
*   **Integration Plan:**
    *   Add a `paper_claim_audit` method to `ComplianceService` or `ReviewService`.
    *   **Behavior:** Extracts quantitative claims from `main.tex` and cross-references them against the generated CSV/JSON results in the `output/` directory to detect and flag AI "hallucinations".

### 7.5 Auto-Fix for TeX (LaTeX 自动化编译容错与修复)
*   **Missing Link:** `LatexService` catches compilation errors but merely reports them.
*   **Integration Plan:**
    *   Add an `auto_fix_compile` method to `LatexService`.
    *   **Behavior:** Passes the parsed `xelatex` error log (e.g., `Missing $ inserted`) back to `AIService` with the surrounding `.tex` context to automatically generate and apply a patch to `main.tex`, then recompiles.

### 7.6 Vision-Based Figure Audit (基于视觉的图表规范审查)
*   **Missing Link:** The backend lacks multi-modal integration to visually inspect generated charts.
*   **Integration Plan:**
    *   Create a new `FigureAuditService`.
    *   **Behavior:** Uses Gemini's vision capabilities to analyze PNG/PDF files in `output/figures/`. Checks for visual compliance: colorblind-safe palettes, 10pt font size matching the main text, complete legends, and correct "three-line table" formats.

### 7.7 Historical Reference RAG (历史高分论文 RAG 注入)
*   **Missing Link:** Excellent past papers exist in `docs/` but are not actively used during the generation of the current paper.
*   **Integration Plan:**
    *   Integrate a lightweight Retrieval-Augmented Generation (RAG) mechanism into `AIService.stage_write`.
    *   **Behavior:** Uses the `paper-reference` skill to pull structural skeletons, professional terminology, and "golden formulas" for abstracts from highly-rated past papers matching the current problem type, injecting them into the writing prompt.

### 7.8 Submission Nuances (细颗粒度的提交物打包)
*   **Missing Link:** `SubmissionService` creates a generic ZIP file, ignoring strict provincial/national contest formats.
*   **Integration Plan:**
    *   Enhance `SubmissionService.pack_submission`.
    *   **Behavior:** Add rules for generating `.rar` files, compiling an MD5 checksum manifest, stripping `.git` and `__pycache__` folders, and ensuring the exact folder hierarchy demanded by specific contest rulebooks (e.g., separate 'Source Code' and 'Results' directories).

### 7.9 Research Wiki & Knowledge Accumulation (赛后知识沉淀)
*   **Missing Link:** No mechanism to archive learnings after a competition ends.
*   **Integration Plan:**
    *   Create a `KnowledgeService` or `POST /api/v1/workspaces/{workspace_id}/archive` endpoint.
    *   **Behavior:** Post-competition, an AI summarizes the modeling approach, code snippets, and mistakes (from the review logs) and appends a new markdown entry to a global knowledge base for future use.
