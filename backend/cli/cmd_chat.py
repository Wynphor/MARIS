"""
CLI: mathmodel chat [--provider deepseek|mimo] [--context paper|code|data]

Interactive multi-turn conversation with AI.
Maintains conversation context across turns.
Reads workspace files as context.
"""
import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.common import ensure_backend_path, find_workspace_root
ensure_backend_path()

from app.services.api_client_service import APIClientService
from app.core.prompts import read_workspace_file, get_model_for_stage
from app.core.config import settings


HELP_TEXT = """
  Commands:
    /paper      - Include paper/main.tex as context
    /code       - Include src/*.py as context
    /data       - Include data preview as context
    /decompose  - Include problem_decomposition.md
    /model      - Include model_recommendation.md
    /clear      - Clear conversation history
    /save       - Save conversation to chat_history.md
    /exit       - Exit chat

  Just type your message to chat with the AI.
"""


async def chat_loop(ws_id: str, provider: str):
    """Run interactive chat loop."""
    conversation = []  # [{role, content}]

    # Default system prompt
    system_prompt = (
        "You are a math modeling competition assistant. "
        "You help with problem analysis, model selection, code generation, "
        "paper writing, and review. Be concise and actionable. "
        "When generating LaTeX, use proper math notation. "
        "When generating Python, include imports and print statements."
    )

    config = get_model_for_stage("chat") if provider == "auto" else {
        "provider": provider, "model": None
    }

    print("\n  MathModel-Engine Chat")
    print(f"  Provider: {config['provider']}")
    print(f"  Workspace: {ws_id}")
    print(HELP_TEXT)

    while True:
        try:
            user_input = input("\n  You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd == "/exit":
                print("  Bye!")
                break

            elif cmd == "/clear":
                conversation.clear()
                print("  Conversation cleared.")
                continue

            elif cmd == "/help":
                print(HELP_TEXT)
                continue

            elif cmd == "/paper":
                content = read_workspace_file(ws_id, "paper/main.tex")
                if content:
                    conversation.append({
                        "role": "user",
                        "content": f"[Attached: paper/main.tex]\n```\n{content[:8000]}\n```"
                    })
                    print(f"  Attached paper/main.tex ({len(content)} chars)")
                else:
                    print("  No paper/main.tex found.")
                continue

            elif cmd == "/code":
                src_dir = settings.DATA_DIR / ws_id / "src"
                if src_dir.exists():
                    code_parts = []
                    for py in sorted(src_dir.glob("*.py")):
                        code = py.read_text(encoding="utf-8", errors="replace")
                        code_parts.append(f"### {py.name}\n```python\n{code[:3000]}\n```")
                    if code_parts:
                        conversation.append({
                            "role": "user",
                            "content": f"[Attached: src/*.py]\n\n" + "\n\n".join(code_parts)
                        })
                        print(f"  Attached {len(code_parts)} Python files")
                    else:
                        print("  No Python files found in src/")
                else:
                    print("  No src/ directory found.")
                continue

            elif cmd == "/data":
                raw_dir = settings.DATA_DIR / ws_id / "data" / "raw"
                if raw_dir.exists():
                    import pandas as pd
                    for f in list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.xlsx")):
                        try:
                            if f.suffix == ".csv":
                                df = pd.read_csv(f, nrows=20)
                            else:
                                df = pd.read_excel(f, nrows=20)
                            preview = f"[Attached: {f.name}]\n"
                            preview += f"Columns: {list(df.columns)}\n"
                            preview += f"Shape: {df.shape}\n"
                            preview += df.head(10).to_string()
                            conversation.append({"role": "user", "content": preview})
                            print(f"  Attached {f.name} ({df.shape[0]} rows preview)")
                            break
                        except Exception:
                            continue
                else:
                    print("  No data files found.")
                continue

            elif cmd == "/decompose":
                content = read_workspace_file(ws_id, "problem_decomposition.md")
                if content:
                    conversation.append({"role": "user", "content": f"[Attached: problem_decomposition.md]\n{content}"})
                    print(f"  Attached problem_decomposition.md")
                else:
                    print("  No decomposition found. Run 'decompose' first.")
                continue

            elif cmd == "/model":
                content = read_workspace_file(ws_id, "model_recommendation.md")
                if content:
                    conversation.append({"role": "user", "content": f"[Attached: model_recommendation.md]\n{content}"})
                    print(f"  Attached model_recommendation.md")
                else:
                    print("  No model recommendation found. Run 'model-select' first.")
                continue

            elif cmd == "/save":
                save_path = settings.DATA_DIR / ws_id / "chat_history.md"
                lines = ["# Chat History\n"]
                for msg in conversation:
                    role = "User" if msg["role"] == "user" else "AI"
                    lines.append(f"## {role}\n{msg['content']}\n")
                save_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"  Saved to {save_path}")
                continue

            else:
                print(f"  Unknown command: {cmd}. Type /help for commands.")
                continue

        # Add user message to conversation
        conversation.append({"role": "user", "content": user_input})

        # Build prompt with conversation history
        history_text = ""
        for msg in conversation[-10:]:  # Last 10 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"\n{role}: {msg['content']}\n"

        user_prompt = f"Conversation history:\n{history_text}\n\nPlease respond to the latest message."

        # Stream response
        print("\n  AI> ", end="", flush=True)
        response_text = ""
        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=ws_id,
            stage="chat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config.get("model"),
            temperature=0.4,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                content = chunk[6:]
                print(content, end="", flush=True)
                response_text += content

        print()  # Newline after response

        # Add AI response to conversation
        if response_text.strip():
            conversation.append({"role": "assistant", "content": response_text.strip()})


def main():
    parser = argparse.ArgumentParser(description="Interactive AI chat")
    parser.add_argument("--workspace", "-w", default="", help="Workspace ID")
    parser.add_argument("--provider", "-p", default="auto", help="LLM provider (deepseek/mimo/auto)")
    args = parser.parse_args()

    ws_id = args.workspace
    if not ws_id:
        ws_root = find_workspace_root()
        if ws_root:
            ws_id = ws_root.name
        else:
            data_dir = Path("data")
            if data_dir.exists():
                ws_dirs = sorted(data_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)
                for d in ws_dirs:
                    if d.is_dir() and (d / "config.json").exists():
                        ws_id = d.name
                        break
        if not ws_id:
            print("Error: No workspace found. Use --workspace or run from a workspace directory.")
            sys.exit(1)

    asyncio.run(chat_loop(ws_id, args.provider))


if __name__ == "__main__":
    main()
