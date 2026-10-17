"""
CLI common utilities — workspace detection, stream printing, async helpers.
"""
import os
import sys
import json
import asyncio
from pathlib import Path


def find_workspace_root() -> Path | None:
    """Find workspace root by looking for config.json in cwd and parents."""
    current = Path.cwd()
    for d in [current, *current.parents]:
        if (d / "config.json").exists() and (d / "data").is_dir():
            return d
        # Also check if we're inside a workspace (has data/raw, src, paper)
        if all((d / sub).exists() for sub in ("src", "paper")):
            return d
    return None


def get_workspace_id(ws_root: Path) -> str:
    """Extract workspace ID from the workspace root directory name."""
    return ws_root.name


def ensure_backend_path():
    """Ensure backend/app is on sys.path."""
    backend_dir = Path(__file__).resolve().parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.chdir(backend_dir)


def print_banner(title: str):
    """Print a section banner."""
    line = "=" * 50
    print(f"\n{line}")
    print(f"  {title}")
    print(f{line}\n")


def print_status(ws_id: str, ws_status: str, stages_done: list[str], stages_remaining: list[str]):
    """Print workspace status in a readable format."""
    print(f"\n  Workspace: {ws_id}")
    print(f"  Status:    {ws_status}")
    print(f"  Progress:  {len(stages_done)}/{len(stages_done) + len(stages_remaining)} stages")
    if stages_done:
        print(f"  Done:      {', '.join(stages_done[-5:])}")
    if stages_remaining:
        print(f"  Next:      {stages_remaining[0]}")
    print()


async def consume_stream(gen, print_output: bool = True) -> str:
    """Consume an async SSE generator, print output, return collected text."""
    collected = []
    async for chunk in gen:
        if not isinstance(chunk, str):
            chunk = str(chunk)

        # Extract content from SSE format
        if chunk.startswith("data: "):
            content = chunk[6:].strip()
        else:
            content = chunk.strip()

        if not content:
            continue

        # Skip system tags for display
        skip_tags = ("[TASK]", "[STATS]", "[TASK_COMPLETE]", "[SAVED]")
        if any(content.startswith(tag) for tag in skip_tags):
            continue

        # Print to stdout
        if print_output:
            print(content)

        # Collect non-system content
        if not any(content.startswith("[") for tag in
                   ["[INFO]", "[STEP", "[ERROR]", "[WARNING]", "[SUCCESS]",
                    "[RED TEAM]", "[BLUE TEAM]", "[ROUND", "[RESULT]",
                    "[MISSING]", "[OUTLIER]", "[STD]", "[OUTPUT]",
                    "[FIGURE]", "[GRAPH]", "[SUMMARY]", "[STATUS]",
                    "[COMPILE", "[DONE]"]):
            collected.append(content)

    return "\n".join(collected)
