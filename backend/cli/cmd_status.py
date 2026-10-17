"""
CLI: mathmodel status [--workspace <id>]

Show workspace status, progress, and next steps.
"""
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.common import ensure_backend_path, find_workspace_root, print_status
ensure_backend_path()

from app.db.database import create_db_and_tables, engine
from app.models.workspace import Workspace
from app.services.task_service import TaskService
from app.services.competition_config_service import CompetitionConfigService
from sqlmodel import Session


STAGE_ORDER = [
    "decompose", "model-select", "paper-ref", "code-gen", "figure-gen",
    "write", "compile", "review", "format-check", "claim-audit",
    "auto-improve", "validate", "pack", "archive",
]

STATUS_TO_STAGE = {
    "INIT": 0, "DECOMPOSED": 1, "MODELED": 2, "CODED": 4,
    "WRITTEN": 5, "REVIEWED": 7, "CHECKED": 8, "IMPROVED": 10,
    "PACKED": 12, "FINISHED": 14,
}


def main():
    parser = argparse.ArgumentParser(description="Show workspace status")
    parser.add_argument("--workspace", "-w", default="", help="Workspace ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    create_db_and_tables()

    # Find workspace
    ws_id = args.workspace
    if not ws_id:
        ws_root = find_workspace_root()
        if ws_root:
            ws_id = ws_root.name
        else:
            print("Error: No workspace found. Run from a workspace directory or use --workspace.")
            sys.exit(1)

    with Session(engine) as session:
        ws = session.get(Workspace, ws_id)
        if not ws:
            print(f"Error: Workspace '{ws_id}' not found.")
            sys.exit(1)

    # Get config
    config = CompetitionConfigService.get_config(ws_id)

    # Determine progress
    current_idx = STATUS_TO_STAGE.get(ws.status, 0)
    stages_done = STAGE_ORDER[:current_idx]
    stages_remaining = STAGE_ORDER[current_idx:]

    # Get recent tasks
    tasks = TaskService.get_workspace_tasks(ws_id, limit=5)

    if args.json:
        print(json.dumps({
            "workspace_id": ws_id,
            "title": ws.title,
            "status": ws.status,
            "config": config,
            "stages_done": stages_done,
            "stages_remaining": stages_remaining,
            "recent_tasks": [
                {"stage": t.stage, "status": t.status, "duration": t.duration_seconds}
                for t in tasks
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n  {'='*50}")
        print(f"  MathModel-Engine: {ws.title}")
        print(f"  {'='*50}")
        print(f"  ID:          {ws_id}")
        print(f"  Status:      {ws.status}")
        print(f"  Competition: {config.get('competition_type', '?')}")
        print(f"  Problem:     {config.get('problem_id', '?')} - {config.get('problem_title', ws.title)}")
        print(f"  Progress:    {len(stages_done)}/{len(STAGE_ORDER)} stages")

        # Progress bar
        bar_len = 30
        filled = int(bar_len * len(stages_done) / len(STAGE_ORDER))
        bar = "█" * filled + "░" * (bar_len - filled)
        pct = int(100 * len(stages_done) / len(STAGE_ORDER))
        print(f"  [{bar}] {pct}%")

        if stages_remaining:
            print(f"\n  Next: {stages_remaining[0]}")
            print(f"  Command: python -m cli.cmd_stage {stages_remaining[0]}")
        else:
            print(f"\n  All stages complete! Ready to submit.")

        if tasks:
            print(f"\n  Recent tasks:")
            for t in tasks:
                dur = f"{t.duration_seconds:.1f}s" if t.duration_seconds else "-"
                print(f"    {t.stage:20s} {t.status:12s} {dur}")

        # File stats
        ws_path = Path("data") / ws_id
        py_count = len(list((ws_path / "src").glob("*.py"))) if (ws_path / "src").exists() else 0
        tex_count = len(list((ws_path / "paper").glob("*.tex"))) if (ws_path / "paper").exists() else 0
        fig_count = len(list((ws_path / "output" / "figures").glob("*"))) if (ws_path / "output" / "figures").exists() else 0
        data_count = len(list((ws_path / "data" / "raw").glob("*"))) if (ws_path / "data" / "raw").exists() else 0

        print(f"\n  Files: {py_count} .py | {tex_count} .tex | {fig_count} figures | {data_count} data files")
        print()


if __name__ == "__main__":
    main()
