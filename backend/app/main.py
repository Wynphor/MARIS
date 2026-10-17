"""
MathModel-Engine FastAPI Application

Production features:
  - Structured logging (replaces print)
  - Request timing middleware
  - Real health check (DB connectivity)
  - Graceful shutdown (engine disposal)
  - Startup API key warning
"""
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .api.routes import workspaces, pipeline, editor, tasks, system
from .db.database import create_db_and_tables, engine
from .core.exceptions import AppError, app_error_handler, generic_error_handler
from .core.logging import setup_logging, get_logger
from .core.config import settings

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理。"""
    setup_logging()

    # ── 启动 ──
    logger.info("MathModel-Engine starting up...")
    try:
        create_db_and_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        raise

    # Warn if no API keys configured
    configured_keys = [
        name for name in ("MIMO", "DEEPSEEK", "OPENAI", "CLAUDE", "GEMINI", "GROK")
        if getattr(settings, f"{name}_API_KEY", "")
    ]
    if configured_keys:
        logger.info("Configured LLM providers: %s", ", ".join(configured_keys))
    else:
        logger.warning(
            "No LLM API keys configured! AI stages will fail at runtime. "
            "Set at least one key in .env (e.g. DEEPSEEK_API_KEY)."
        )

    yield

    # ── 关闭 ──
    logger.info("MathModel-Engine shutting down...")
    engine.dispose()
    logger.info("Database connection pool disposed")


app = FastAPI(
    title="MathModel-Engine API",
    description=(
        "数学建模竞赛自动化后端。支持赛题拆解、模型推荐、代码生成、"
        "论文写作、对抗审查、自动改进、格式检查、提交打包等全流程。"
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# ── Request logging middleware ──

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, status, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    # Skip noisy health check and docs requests
    path = request.url.path
    if path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return response

    log_fn = logger.warning if response.status_code >= 400 else logger.info
    log_fn(
        "%s %s → %d (%.0fms)",
        request.method,
        path,
        response.status_code,
        duration_ms,
    )
    return response

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(editor.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")

# 统一异常处理
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)


@app.get("/")
async def root():
    return {
        "message": "MathModel-Engine API is running",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "workspaces": "/api/v1/workspaces",
            "pipeline": "/api/v1/pipeline/execute",
            "stages": "/api/v1/pipeline/stages",
            "editor": "/api/v1/editor",
            "tasks": "/api/v1/tasks",
        },
    }


@app.get("/health")
async def health_check():
    """Real health check: verify DB connectivity."""
    from sqlmodel import Session as DBSession, text
    try:
        with DBSession(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "healthy", "version": "2.0.0", "database": "ok"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return {"status": "unhealthy", "version": "2.0.0", "database": str(e)}


@app.get("/ready")
async def readiness_check():
    """Readiness check: DB + at least one LLM key configured."""
    from sqlmodel import Session as DBSession, text

    checks = {"database": "unknown", "llm_keys": "unknown"}
    ready = True

    # DB check
    try:
        with DBSession(engine) as session:
            session.exec(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = str(e)
        ready = False

    # LLM key check
    has_key = any(
        getattr(settings, f"{name}_API_KEY", "")
        for name in ("MIMO", "DEEPSEEK", "OPENAI", "CLAUDE", "GEMINI", "GROK")
    )
    checks["llm_keys"] = "ok" if has_key else "no_keys_configured"
    if not has_key:
        ready = False

    status_code = 200 if ready else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"ready": ready, "checks": checks},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
