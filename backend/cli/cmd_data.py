"""
CLI: mathmodel data <file> [--head N] [--describe] [--columns]

Explore data files (CSV/Excel) interactively.
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.common import ensure_backend_path, find_workspace_root
ensure_backend_path()


def main():
    parser = argparse.ArgumentParser(description="Explore data files")
    parser.add_argument("file", nargs="?", help="Data file path (CSV/Excel)")
    parser.add_argument("--workspace", "-w", default="", help="Workspace ID")
    parser.add_argument("--head", "-n", type=int, default=10, help="Show first N rows")
    parser.add_argument("--describe", "-d", action="store_true", help="Show statistics")
    parser.add_argument("--columns", "-c", action="store_true", help="Show column info")
    parser.add_argument("--sample", "-s", type=int, default=0, help="Random sample N rows")
    args = parser.parse_args()

    # Find file
    file_path = None
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            # Try in workspace data/raw/
            ws_id = args.workspace
            if not ws_id:
                ws_root = find_workspace_root()
                if ws_root:
                    ws_id = ws_root.name
            if ws_id:
                candidate = Path("data") / ws_id / "data" / "raw" / args.file
                if candidate.exists():
                    file_path = candidate
                candidate2 = Path("data") / ws_id / args.file
                if candidate2.exists():
                    file_path = candidate2
    else:
        # Auto-find data files in workspace
        ws_id = args.workspace
        if not ws_id:
            ws_root = find_workspace_root()
            if ws_root:
                ws_id = ws_root.name
        if ws_id:
            raw_dir = Path("data") / ws_id / "data" / "raw"
            if raw_dir.exists():
                data_files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.xlsx"))
                if data_files:
                    file_path = data_files[0]
                    print(f"Auto-detected: {file_path}")

    if not file_path or not file_path.exists():
        print("Error: No data file found.")
        print("  Usage: python -m cli.cmd_data <file.csv>")
        print("  Or place CSV/Excel files in data/<workspace>/data/raw/")
        sys.exit(1)

    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas not installed. Run: pip install pandas openpyxl")
        sys.exit(1)

    # Load data
    ext = file_path.suffix.lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif ext == ".csv":
            # Try multiple encodings
            for enc in ["utf-8", "gbk", "gb2312", "latin1"]:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print("Error: Could not decode CSV file.")
                sys.exit(1)
        else:
            print(f"Error: Unsupported file type: {ext}")
            sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Display
    print(f"\n  File: {file_path.name}")
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")

    if args.columns:
        print(f"\n  Columns:")
        for i, col in enumerate(df.columns):
            dtype = df[col].dtype
            null_count = df[col].isnull().sum()
            null_pct = null_count / len(df) * 100
            print(f"    {i+1:3d}. {col:30s} {str(dtype):10s} null: {null_count} ({null_pct:.1f}%)")

    if args.describe:
        print(f"\n  Statistics:")
        desc = df.describe(include="all")
        print(desc.to_string(max_cols=10))

    # Show head
    if not args.describe or args.head:
        n = args.sample if args.sample else args.head
        print(f"\n  {'First' if not args.sample else 'Random'} {n} rows:")
        if args.sample:
            print(df.sample(min(n, len(df))).to_string(max_cols=10))
        else:
            print(df.head(n).to_string(max_cols=10))

    print()


if __name__ == "__main__":
    main()
