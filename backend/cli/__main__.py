"""
MathModel-Engine CLI — 统一入口

Usage: python -m cli <command> [options]

Commands:
    init <title>        Create a new workspace
    status              Show workspace status and progress
    <stage>             Execute a pipeline stage (decompose, model-select, ...)
    run-all             Execute full pipeline
    chat                Interactive AI conversation
    data <file>         Explore data files

Pipeline stages:
    decompose           Problem decomposition
    model-select        Model recommendation
    paper-ref           Award-winning paper reference search
    code-gen            Code generation
    figure-gen          Figure generation
    write               Paper writing (auto LaTeX compile)
    compile             LaTeX compilation
    review              Adversarial review (red/blue team)
    format-check        Format compliance check
    claim-audit         Numerical claim audit
    citation-audit      Citation audit
    auto-improve        Auto-improvement loop
    validate            Sensitivity analysis
    pack                Package for submission

Examples:
    python -m cli init "自驾行程规划" --type 国赛 --id C
    python -m cli data problem_data.csv
    python -m cli decompose problem.pdf
    python -m cli model-select
    python -m cli code-gen
    python -m cli write
    python -m cli review --rounds 2
    python -m cli compile
    python -m cli pack
    python -m cli chat
    python -m cli status
"""
import sys

COMMANDS = {
    "init": "cli.cmd_init",
    "status": "cli.cmd_status",
    "chat": "cli.cmd_chat",
    "data": "cli.cmd_data",
}

# All pipeline stages route to cmd_stage
STAGES = {
    "decompose", "model-select", "paper-ref", "code-gen", "figure-gen",
    "write", "compile", "review", "format-check", "claim-audit",
    "citation-audit", "auto-improve", "validate", "figures",
    "pack", "archive", "preprocess", "ingest", "audit", "run-all",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]

    # Shift argv so the subcommand's argparse works correctly
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command in COMMANDS:
        module = __import__(COMMANDS[command], fromlist=["main"])
        module.main()
    elif command in STAGES:
        # Insert stage as positional arg
        sys.argv = [f"cli.cmd_stage", command] + sys.argv
        from cli.cmd_stage import main
        main()
    else:
        print(f"Unknown command: {command}")
        print("Run 'python -m cli help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
