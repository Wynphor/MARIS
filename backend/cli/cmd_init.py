"""
CLI: mathmodel init <title> [--type 国赛|美赛|研赛] [--id C|D|E]

Create a new workspace with standard directory structure.
"""
import sys
import argparse
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))

from common import ensure_backend_path, print_banner
ensure_backend_path()

from app.db.database import create_db_and_tables
from app.models.workspace import WorkspaceCreate
from app.services.workspace_service import WorkspaceService
from app.services.competition_config_service import CompetitionConfigService
from app.db.database import engine
from sqlmodel import Session


def main():
    parser = argparse.ArgumentParser(description="Create a new math modeling workspace")
    parser.add_argument("title", help="Workspace title (e.g., '自驾行程规划')")
    parser.add_argument("--type", default="国赛", help="Competition type: 国赛/美赛/研赛")
    parser.add_argument("--id", default="", help="Problem ID: C/D/E")
    args = parser.parse_args()

    create_db_and_tables()

    ws_data = WorkspaceCreate(
        title=args.title,
        question_id=args.id,
        problem_type=args.type,
    )

    ws = WorkspaceService.create_workspace_folder(ws_data)
    CompetitionConfigService.init_workspace(ws.id)

    with Session(engine) as session:
        session.add(ws)
        session.commit()

    # Update config with competition info
    CompetitionConfigService.update_config(ws.id, {
        "competition_type": args.type,
        "problem_id": args.id,
        "problem_title": args.title,
    })

    print_banner(f"Workspace Created: {ws.id}")
    print(f"  Title:     {args.title}")
    print(f"  Type:      {args.type}")
    print(f"  Problem:   {args.id or '(not set)'}")
    print(f"  Directory: data/{ws.id}/")
    print(f"\n  Next steps:")
    print(f"    1. Copy problem PDF to data/{ws.id}/problem.pdf")
    print(f"    2. Copy data files to data/{ws_id}/data/raw/")
    print(f"    3. Run: python -m cli.decompose problem.pdf")
    print()

    # Write workspace ID to .mathmodel file for auto-detection
    ws_file = __import__("pathlib").Path("data") / ws.id / ".mathmodel"
    ws_file.write_text(ws.id, encoding="utf-8")

    return ws.id


if __name__ == "__main__":
    main()
