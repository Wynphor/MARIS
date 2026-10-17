from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse, FileResponse
from ...services.latex_service import LatexService
from ...services.python_runner import PythonRunner
from ...services.api_client_service import APIClientService
from ...core.config import settings
from pathlib import Path
import difflib

router = APIRouter(prefix="/editor", tags=["editor"])

DATA_DIR = settings.DATA_DIR


@router.get("/files/{workspace_id}/{file_path:path}")
async def read_file(workspace_id: str, file_path: str):
    ws_path = (DATA_DIR / workspace_id).resolve()
    full_path = (ws_path / file_path).resolve()

    # Prevent path traversal
    if not str(full_path).startswith(str(ws_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # If it's a text file, return content. If binary, return FileResponse.
    ext = full_path.suffix.lower()
    if ext in [".md", ".py", ".tex", ".txt", ".json"]:
        with open(full_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    else:
        return FileResponse(full_path)


@router.put("/files/{workspace_id}/{file_path:path}")
async def save_file(
    workspace_id: str, file_path: str, content: str = Body(..., embed=True)
):
    ws_path = (DATA_DIR / workspace_id).resolve()
    full_path = (ws_path / file_path).resolve()

    # Prevent path traversal
    if not str(full_path).startswith(str(ws_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# UX-7: Diff comparison
# ============================================================

@router.get("/diff/{workspace_id}/{file_path:path}")
async def get_file_diff(workspace_id: str, file_path: str, lines: int = 50):
    """
    Get unified diff showing recent changes to a file.
    Returns the diff between the current file and its last saved version
    (from the most recent pipeline task output that touched this file).
    """
    ws_path = (DATA_DIR / workspace_id).resolve()
    full_path = (ws_path / file_path).resolve()

    if not str(full_path).startswith(str(ws_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    with open(full_path, "r", encoding="utf-8") as f:
        current_lines = f.readlines()

    # Look for a .bak version (created by output_persistence_service)
    bak_path = full_path.with_suffix(full_path.suffix + ".bak")
    if bak_path.exists():
        with open(bak_path, "r", encoding="utf-8") as f:
            old_lines = f.readlines()
    else:
        # No backup = first version, treat as "no changes"
        return {
            "file": file_path,
            "has_changes": False,
            "diff_lines": 0,
            "diff": "(first version — no previous version to compare)",
        }

    diff = list(difflib.unified_diff(
        old_lines, current_lines,
        fromfile=f"a/{file_path} (previous)",
        tofile=f"b/{file_path} (current)",
        n=3
    ))

    return {
        "file": file_path,
        "has_changes": len(diff) > 0,
        "diff_lines": len(diff),
        "diff": "".join(diff[-lines:]) if diff else "(no changes)",
    }


# ============================================================
# UX-6: AI incremental edit
# ============================================================

@router.post("/ai-edit/{workspace_id}/{file_path:path}")
async def ai_incremental_edit(
    workspace_id: str,
    file_path: str,
    instruction: str = Body(..., embed=True),
):
    """
    AI-driven incremental edit: send a natural language instruction
    (e.g., "修改第三章的结论，加入灵敏度分析的内容"),
    and the AI modifies only the relevant part of the file.
    """
    ws_path = (DATA_DIR / workspace_id).resolve()
    full_path = (ws_path / file_path).resolve()

    if not str(full_path).startswith(str(ws_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    with open(full_path, "r", encoding="utf-8") as f:
        current_content = f.read()

    ext = full_path.suffix.lower()

    # Build the AI prompt for incremental editing
    system_prompt = (
        "You are a LaTeX/Markdown/Python editor. The user will give you the current "
        "file content and an instruction. You must:\n"
        "1. Make ONLY the changes described in the instruction.\n"
        "2. Preserve everything else exactly as-is.\n"
        "3. Return ONLY the complete modified file content, no explanations.\n"
        "4. Do NOT wrap in markdown code blocks."
    )

    user_prompt = (
        f"File: {file_path}\n"
        f"Instruction: {instruction}\n\n"
        f"Current content:\n```\n{current_content}\n```"
    )

    # Collect AI output
    result = await APIClientService.call_and_collect(
        provider="mimo",
        workspace_id=workspace_id,
        stage="ai-edit",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name="mimo-v2-pro",
    )

    if not result or len(result) < 10:
        raise HTTPException(status_code=500, detail="AI returned empty or too short response")

    # Save backup before overwriting
    import shutil
    bak_path = full_path.with_suffix(full_path.suffix + ".bak")
    shutil.copy2(full_path, bak_path)

    # Save new content
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(result)

    # Compute diff
    old_lines = current_content.splitlines(keepends=True)
    new_lines = result.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{file_path} (before)",
        tofile=f"b/{file_path} (after)",
        n=3
    ))

    return {
        "status": "success",
        "file": file_path,
        "instruction": instruction,
        "old_size": len(current_content),
        "new_size": len(result),
        "diff_preview": "".join(diff[:80]) if diff else "(no visible diff)",
    }


@router.post("/run/{workspace_id}")
async def run_solver(workspace_id: str, script: str = "solve_all.py"):
    return StreamingResponse(
        PythonRunner.run_solver(workspace_id, script),
        media_type="text/event-stream",
    )


@router.post("/compile/{workspace_id}")
async def compile_paper(workspace_id: str, tex_file: str = "main.tex"):
    result = await LatexService.post_process_and_compile(workspace_id, tex_file)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
