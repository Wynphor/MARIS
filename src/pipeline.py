#!/usr/bin/env python3
"""
数学建模竞赛一键流程编排
用法: python pipeline.py --problem <赛题md> --question <题号> [--stage <阶段名>]

模型分工:
  Gemini (Antigravity) → 赛题拆解, 模型推荐, 代码生成, 公式推导, 论文写作, 图表设计, 对抗性审查 (gemini CLI)
  MiMo Pro → 查新, 声明转化, 流程图, 审稿攻击, 自动改进  (mimo_client)
  MiMo V2.5 → 搜索, 格式化, 脚本管理, 统计, 格式检查  (mimo_client)

环境变量:
  MIMO_API_KEY   — MiMo API key
  MIMO_BASE_URL  — MiMo API endpoint (默认 minimax 官方)
"""
import argparse
import subprocess
import sys
import os
import io
from pathlib import Path

# 解决 Windows 控制台默认 GBK 编码打印 UTF-8 字符导致的 UnicodeEncodeError 崩溃
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
PAPER = ROOT / "paper"

# 尝试导入 MiMo 客户端
try:
    from mimo_client import call_mimo, get_model
    MIMO_AVAILABLE = bool(os.environ.get("MIMO_API_KEY"))
except ImportError:
    MIMO_AVAILABLE = False


def _mimo(task: str, prompt: str) -> str:
    """调用 MiMo。若不可用则回退到 Gemini。"""
    if MIMO_AVAILABLE:
        model = get_model(task)
        print(f"  [MiMo] {model} → {task}")
        return call_mimo(prompt, model, task=task)
    else:
        print(f"  [Gemini] (fallback) → {task}")
        return _gemini(prompt)


def _gemini(prompt: str) -> str:
    """调用 Gemini (Antigravity) CLI。"""
    subprocess.run(
        ["gemini", "--skip-trust", "-p", prompt],
        cwd=ROOT, check=False,
        shell=sys.platform.startswith("win")
    )


STAGES = [
    "decompose", "model-select", "code-gen", "preprocess",
    "solve", "sensitivity", "figures", "reference",
    "write", "review", "format-check", "pack",
]


# ============================================================
def stage_decompose(problem_path, question):
    print(f"[1/12] problem-decompose (Gemini): {problem_path}")
    _gemini(
        f"读取 {problem_path}，使用 skills-mathmodel/problem-decompose 拆解赛题。"
        f"同时调用 research-lit 搜索类似赛题文献。输出 problem_decomposition.md"
    )

def stage_model_select():
    print("[2/12] model-select (Gemini)")
    _gemini(
        "使用 skills-mathmodel/model-select 读取 problem_decomposition.md。"
        "调用 idea-creator 构思创新方向，research-wiki 查询历史经验，research-refine 细化方案。"
        "输出 model_recommendation.md"
    )

def stage_code_gen(question):
    print(f"[3/12] code-template (Gemini) → src/problem_{question}/")
    _gemini(
        f"使用 skills-mathmodel/code-template 读取 model_recommendation.md。"
        f"调用 experiment-plan 规划参数矩阵，experiment-bridge 桥接实现。"
        f"输出 src/problem_{question}/ 下的 Python 脚本"
    )

def stage_preprocess(data_path=None):
    print("[4/12] data-preprocess")
    if not data_path or not Path(data_path).exists():
        print("  [SKIP] 无原始数据文件")
        return
    _gemini(f"使用 skills-mathmodel/data-preprocess 处理 {data_path}")

def stage_solve(question):
    print(f"[5/12] solve: src/problem_{question}/")
    script_dir = SRC / f"problem_{question}"
    if not script_dir.exists():
        print("  [SKIP] 无脚本")
        return
    for py_file in sorted(script_dir.glob("*.py")):
        print(f"  Running: {py_file.name}")
        subprocess.run([sys.executable, str(py_file)], cwd=ROOT, check=False)

def stage_sensitivity(question):
    print(f"[6/12] sensitivity-analysis (Gemini)")
    _gemini(
        f"使用 skills/sensitivity-analysis 分析 src/problem_{question}/ 的求解结果，"
        f"输出参数扫描结果图表、模型鲁棒性结论并撰写 sensitivity_report.md。然后使用 result-to-claim 生成论文声明。"
    )

def stage_figures():
    print("[7/12] figures (Gemini)")
    _gemini("使用 skills/paper-figure 生成数据驱动图表到 output/figures/")
    _gemini("使用 skills/figure-spec + skills/mermaid-diagram 生成架构图与流程图到 output/figures/")
    print("  [人工] 图表就绪后，使用 Gemini 审查图表质量")

def stage_reference(problem_type, keywords=""):
    print(f"[8/12] paper-reference (MiMo): {problem_type}")
    _gemini(
        f"使用 skills/paper-reference 检索 {problem_type} 类型的国赛获奖范文"
        f"（关键词: {keywords}），输出 paper_reference_report.md"
    )

import re

def wrap_tables_in_tex(content):
    pos = 0
    new_content = ""
    tables_wrapped = 0
    while True:
        idx = content.find(r"\begin{tabular}", pos)
        if idx == -1:
            idx = content.find(r"\begin{tabular*", pos) # handle tabular*
        if idx == -1:
            new_content += content[pos:]
            break
        
        new_content += content[pos:idx]
        
        # Check if it is already wrapped in \resizebox.
        lookback = content[max(0, idx-50):idx]
        is_wrapped = r"\resizebox" in lookback
        
        # Find matching \end{tabular} or \end{tabular*}.
        is_starred = r"\begin{tabular*}" in content[idx:idx+20]
        end_tag = r"\end{tabular*}" if is_starred else r"\end{tabular}"
        end_idx = content.find(end_tag, idx)
        
        if end_idx == -1:
            # No matching end tag found, just skip wrapping and append
            new_content += content[idx:idx+len(end_tag)]
            pos = idx + len(end_tag)
            continue
            
        tabular_block = content[idx:end_idx + len(end_tag)]
        if is_wrapped:
            new_content += tabular_block
        else:
            # Wrap it!
            new_content += r"\resizebox{\textwidth}{!}{" + tabular_block + "}"
            tables_wrapped += 1
            
        pos = end_idx + len(end_tag)
    return new_content, tables_wrapped

def inject_appendix_code(tex_path, question):
    script_dir = SRC / f"problem_{question.lower()}"
    if not script_dir.exists():
        script_dir = SRC / f"problem_{question.upper()}"
    if not script_dir.exists():
        print(f"    [WARNING] Script directory for question {question} not found. Skipping code injection.")
        return False
    
    py_files = list(script_dir.glob("solve_all.py"))
    if not py_files:
        py_files = list(script_dir.glob("*.py"))
    
    if not py_files:
        print(f"    [WARNING] No Python scripts found in {script_dir}. Skipping code injection.")
        return False
        
    main_py = py_files[0]
    with open(main_py, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    with open(tex_path, 'r', encoding='utf-8') as f:
        tex_content = f.read()
        
    pattern = r"(\\begin\{lstlisting\}(?:\[.*?\])?\n)(.*?)(\n\\end\{lstlisting\})"
    matches = list(re.finditer(pattern, tex_content, re.DOTALL))
    if matches:
        first_match = matches[0]
        prefix = first_match.group(1)
        suffix = first_match.group(3)
        new_listings = prefix + code_content.strip() + suffix
        start, end = first_match.span()
        new_tex_content = tex_content[:start] + new_listings + tex_content[end:]
        
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(new_tex_content)
        print(f"    [OK] Injected solver {main_py.name} ({len(code_content.splitlines())} lines) into {Path(tex_path).name} Appendix A.")
        return True
    else:
        print(f"    [WARNING] No \\begin{{lstlisting}} found in {Path(tex_path).name} to replace.")
        return False

def check_placeholders(tex_path):
    placeholders = ["此处省略", "推导略", "步骤略", "详见附录", "TODO", "placeholder"]
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    found = [p for p in placeholders if p in content]
    if found:
        print(f"    [WARNING] Found placeholders in {Path(tex_path).name}: {', '.join(found)}")
        return False
    print(f"    [OK] Checked placeholders in {Path(tex_path).name}: None found. Structure is complete!")
    return True

def compile_pdf(tex_path):
    tex_path = Path(tex_path)
    cwd = tex_path.parent
    name = tex_path.name
    print(f"  [Pipeline Compile] Compiling {name} using xelatex...")
    for i in range(2):
        print(f"    Pass {i+1}/2...")
        res = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", name],
            cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            shell=sys.platform.startswith("win")
        )
        if res.returncode != 0:
            print(f"    [WARNING] xelatex returned non-zero code {res.returncode} on pass {i+1}")
    
    pdf_path = tex_path.with_suffix(".pdf")
    if pdf_path.exists():
        print(f"    [OK] Successfully compiled {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
    else:
        print(f"    [ERROR] Failed to compile PDF for {name}")

def post_process_tex(tex_path, question):
    tex_path = Path(tex_path)
    if not tex_path.exists():
        print(f"    [WARNING] TeX file not found: {tex_path}")
        return
        
    print(f"  [Pipeline Post-Process] Processing {tex_path.name}...")
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Remove \bottomrule from thebibliography
    bib_start = content.find(r"\begin{thebibliography}")
    if bib_start != -1:
        bib_end = content.find(r"\end{thebibliography}", bib_start)
        if bib_end != -1:
            bib_segment = content[bib_start:bib_end]
            if r"\bottomrule" in bib_segment:
                bib_segment = bib_segment.replace(r"\bottomrule", "")
                content = content[:bib_start] + bib_segment + content[bib_end:]
                print(f"    [FIX] Removed \\bottomrule from bibliography in {tex_path.name}")

    # 2. Automatically wrap tables in \resizebox
    content, tables_wrapped = wrap_tables_in_tex(content)
    if tables_wrapped > 0:
        print(f"    [FIX] Wrapped {tables_wrapped} table(s) in \\resizebox in {tex_path.name}")
        
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 3. Inject code
    inject_appendix_code(tex_path, question)
    
    # 4. Check placeholders
    check_placeholders(tex_path)

def stage_write():
    print("[9/12] paper-write + paper-compile (Gemini)")
    _gemini(
        "使用 paper-write 基于 model_recommendation.md + paper_reference_report.md "
        "生成论文到 paper/main.tex。注入 skills-mathmodel/paper-write-override.md 章节模板。"
        "完成后 paper-compile 编译 PDF"
    )
    
    # Run post-processing
    post_process_tex(PAPER / "main.tex", args.question)
    post_process_tex(PAPER / "main_article.tex", args.question)
    
    # Programmatically compile twice to ensure absolute correctness
    compile_pdf(PAPER / "main.tex")
    compile_pdf(PAPER / "main_article.tex")

def stage_review():
    print("[10/12] auto-review (Gemini 攻击 → Gemini 防御)")
    _gemini("使用 skills/auto-review-loop-llm 扮演 Gemini 审稿人，按竞赛评分标准审查 paper/main.tex")
    _gemini("使用 skills/kill-argument (Gemini 防御) 逐条反驳并修补论文，然后运行 auto-paper-improvement-loop 自动修改")

def stage_format_check():
    print("[11/12] contest-format (MiMo)")
    _gemini("使用 skills/contest-format 检查 paper/main.tex 格式合规性，输出 format_check_report.md")
    _gemini("使用 skills/paper-claim-audit 验证论文中的数值声明是否有数据支持")
    _gemini("使用 skills/citation-audit 验证参考文献真实性")

def stage_pack(paper_pdf, question):
    print(f"[12/12] submit-pack: {paper_pdf}")
    pack_script = ROOT / "tools" / "pack_submission.py"
    if pack_script.exists():
        print("  [Pipeline Pack] Programmatically running tools/pack_submission.py...")
        subprocess.run([sys.executable, str(pack_script)], cwd=ROOT, check=False)
    else:
        _gemini(f"使用 submit-pack 打包 {paper_pdf} + src/problem_{question}/ → 支撑材料 RAR")
    print("\n" + "=" * 60)
    print("  流程完成。人工确认后上传官方系统。")
    print("=" * 60)


# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="数学建模竞赛一键流程")
    parser.add_argument("--problem", required=True, help="赛题路径")
    parser.add_argument("--question", required=True, help="题号 (C/D/E)")
    parser.add_argument("--stage", choices=STAGES, help="从指定阶段开始")
    parser.add_argument("--problem-type", default="优化类", help="题型")
    parser.add_argument("--keywords", default="", help="题目关键词")
    parser.add_argument("--data", help="原始数据文件路径")
    args = parser.parse_args()

    pipeline_order = [
        ("decompose",   lambda: stage_decompose(args.problem, args.question)),
        ("model-select", stage_model_select),
        ("code-gen",    lambda: stage_code_gen(args.question)),
        ("preprocess",  lambda: stage_preprocess(args.data)),
        ("solve",       lambda: stage_solve(args.question)),
        ("sensitivity", lambda: stage_sensitivity(args.question)),
        ("figures",     stage_figures),
        ("reference",   lambda: stage_reference(args.problem_type, args.keywords)),
        ("write",       stage_write),
        ("review",      stage_review),
        ("format-check", stage_format_check),
        ("pack",        lambda: stage_pack(f"{PAPER}/main.pdf", args.question)),
    ]

    print(f"MiMo API: {'已配置' if MIMO_AVAILABLE else '未配置（回退 DeepSeek）'}")
    print(f"Pipeline from stage: {args.stage or 'decompose'}\n")

    start_idx = 0
    if args.stage:
        for i, (name, _) in enumerate(pipeline_order):
            if name == args.stage:
                start_idx = i
                break

    for name, fn in pipeline_order[start_idx:]:
        print(f"\n{'─' * 50}")
        try:
            fn()
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            resp = input("  Continue? [y/N] ")
            if resp.lower() != "y":
                sys.exit(1)
