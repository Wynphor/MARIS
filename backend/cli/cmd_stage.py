"""
CLI: mathmodel <stage> [options]

Execute a pipeline stage. Supports all 21 stages.

Usage:
    python -m cli.cmd_stage decompose problem.pdf
    python -m cli.cmd_stage model-select
    python -m cli.cmd_stage code-gen
    python -m cli.cmd_stage write
    python -m cli.cmd_stage review --rounds 3
    python -m cli.cmd_stage compile
    python -m cli.cmd_stage pack
    python -m cli.cmd_stage run-all
    python -m cli.cmd_stage preprocess data.csv
    python -m cli.cmd_stage figure-gen
"""
import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.common import ensure_backend_path, find_workspace_root, consume_stream, print_banner
ensure_backend_path()

from app.db.database import create_db_and_tables, engine
from app.models.workspace import Workspace
from app.models.pipeline import PipelineRequest
from app.services.task_service import TaskService
from app.core.config import settings
from sqlmodel import Session


async def run_stage(ws_id: str, stage: str, args):
    """Execute a single pipeline stage and stream output."""
    from app.services.stage_registry import check_dependencies, get_stage_stream
    from app.core.prompts import read_workspace_file

    # Check workspace exists
    with Session(engine) as session:
        ws = session.get(Workspace, ws_id)
        if not ws:
            print(f"Error: Workspace '{ws_id}' not found.")
            return

    # Check dependencies
    try:
        check_dependencies(ws, stage)
    except Exception as e:
        print(f"Dependency error: {e}")
        return

    # Create task
    task = TaskService.create_task(ws_id, stage, mode="CLI")

    # Build request
    req = PipelineRequest(
        workspace_id=ws_id,
        stage=stage,
        mode="CLI",
        keywords=args.keywords or "",
        review_rounds=args.rounds,
    )

    # Get problem text for decompose
    problem_text = ""
    if stage == "decompose":
        # Check for problem file
        for candidate in ["problem.pdf", "problem.md", "problem.txt"]:
            content = read_workspace_file(ws_id, candidate)
            if content:
                problem_text = content
                break
        if not problem_text and args.keywords:
            problem_text = args.keywords
        if not problem_text:
            # Try to read from data/raw/
            raw_dir = settings.DATA_DIR / ws_id / "data" / "raw"
            if raw_dir.exists():
                for f in raw_dir.glob("*"):
                    if f.suffix in (".txt", ".md"):
                        problem_text = f.read_text(encoding="utf-8", errors="replace")
                        break
        if not problem_text:
            print("Error: No problem text found.")
            print("  Place problem.pdf/problem.md in the workspace root,")
            print("  or use: python -m cli.cmd_stage decompose --keywords 'your problem description'")
            return

    # Get stream
    stream = get_stage_stream(stage, req, ws_id, problem_text)
    if stream is None:
        print(f"Stage '{stage}' cannot be run via CLI (requires file parameters).")
        return

    # Wrap with task service and consume
    wrapped = TaskService.wrap_sse_stream(task, stream)
    await consume_stream(wrapped)


async def run_all(ws_id: str, args):
    """Execute the full pipeline."""
    from app.services.stage_registry import DEFAULT_PIPELINE_ORDER, get_stage_stream

    stages = DEFAULT_PIPELINE_ORDER
    if args.stages:
        stages = [s.strip() for s in args.stages.split(",")]

    print_banner(f"Full Pipeline: {len(stages)} stages")
    for i, stage in enumerate(stages, 1):
        print(f"\n{'─'*50}")
        print(f"  [{i}/{len(stages)}] {stage}")
        print(f"{'─'*50}")

        # Create a simple args namespace for each stage
        stage_args = argparse.Namespace(
            keywords=args.keywords if stage == "decompose" else "",
            rounds=getattr(args, "rounds", 2),
        )

        await run_stage(ws_id, stage, stage_args)

    print_banner("Pipeline Complete")
    # Show final status
    from cli.cmd_status import main as status_main
    sys.argv = ["status", "--workspace", ws_id]
    status_main()


def main():
    parser = argparse.ArgumentParser(
        description="MathModel-Engine: Execute pipeline stages",
        usage="%(prog)s <stage> [options]",
    )
    parser.add_argument("stage", help="Stage name (decompose, model-select, code-gen, write, review, compile, pack, run-all, ...)")
    parser.add_argument("--workspace", "-w", default="", help="Workspace ID")
    parser.add_argument("--keywords", "-k", default="", help="Keywords or problem text")
    parser.add_argument("--rounds", "-r", type=int, default=2, help="Review rounds (default: 2)")
    parser.add_argument("--stages", default="", help="Comma-separated stages for run-all")

    # Parse known args (stage-specific args may follow)
    args, remaining = parser.parse_known_args()

    # Find workspace
    ws_id = args.workspace
    if not ws_id:
        ws_root = find_workspace_root()
        if ws_root:
            ws_id = ws_root.name
        else:
            # Try to find most recent workspace
            data_dir = Path("data")
            if data_dir.exists():
                ws_dirs = sorted(data_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)
                for d in ws_dirs:
                    if d.is_dir() and (d / "config.json").exists():
                        ws_id = d.name
                        break

            if not ws_id:
                print("Error: No workspace found.")
                print("  Options:")
                print("    1. Run from a workspace directory")
                print("    2. Use --workspace <id>")
                print("    3. Run 'python -m cli.cmd_init <title>' first")
                sys.exit(1)

    create_db_and_tables()

    # Handle remaining args for specific stages
    if remaining and args.stage == "decompose":
        # First remaining arg might be a problem file path
        problem_path = Path(remaining[0])
        if problem_path.exists():
            # Copy problem file to workspace
            dest = Path("data") / ws_id / f"problem{problem_path.suffix}"
            import shutil
            shutil.copy2(problem_path, dest)
            print(f"Copied {problem_path} → {dest}")

    # Dispatch
    if args.stage == "run-all":
        asyncio.run(run_all(ws_id, args))
    elif args.stage == "status":
        sys.argv = ["status", "--workspace", ws_id]
        from cli.cmd_status import main as status_main
        status_main()
    else:
        print_banner(f"Stage: {args.stage}")
        asyncio.run(run_stage(ws_id, args.stage, args))


if __name__ == "__main__":
    main()
