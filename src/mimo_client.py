"""
MiMo API 调用模块 v2
通过 OpenAI 兼容接口调用 MiMo V2.5 / V2.5-Pro
配置：.env 文件（MIMO_API_KEY + MIMO_BASE_URL）
"""
import os, json, urllib.request, urllib.error, sys, io

# 解决 Windows 控制台默认 GBK 编码打印 UTF-8 字符（如表情符号）导致的 UnicodeEncodeError 崩溃
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.isfile(_ENV_FILE):
    with open(_ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.minimax.chat/v1")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not MIMO_API_KEY:
    print("[WARN] MIMO_API_KEY not set. MiMo falls back to DeepSeek.")


def _extract_response(msg: dict) -> str:
    """优先 content；空则从 reasoning_content 尾部提取结论。"""
    content = msg.get("content", "")
    if content and len(content.strip()) > 20:
        return content.strip()
    reasoning = msg.get("reasoning_content", "")
    if not reasoning:
        return content
    # 取 reasoning 后 60% 作为结论区域
    split = int(len(reasoning) * 0.4)
    tail = reasoning[split:]
    return tail.strip() if tail.strip() else reasoning[-2000:].strip()


SYSTEM_PROMPTS = {
    "auto-review-loop": (
        "你是数学建模竞赛审稿人。按四维度打分（1-10），每项附理由："
        "1.假设合理性 2.建模创造性 3.结果正确性 4.表述清晰度。最后给150字总评。直接输出。"
    ),
    "paper-claim-audit": (
        "你是论文数据核验员。逐条检查数值声明与源数据是否匹配。"
        "输出格式：[PASS/FAIL] 声明 → 证据文件 → 实际值 → 是否一致。直接输出。"
    ),
    "contest-format": (
        "你是数学建模竞赛论文格式检查员。逐行检查LaTeX源码，以下为强制规则："
        "1.表格必须三线表(\\toprule/\\midrule/\\bottomrule)，禁止竖线(|)和\\hline"
        "2.参考文献标注必须用[1][2]格式(natbib numbers)"
        "3.正文和附录不得出现学校、姓名等身份信息"
        "4.目录\\tableofcontents在第1页"
        "5.摘要单独一页(\\begin{abstract}...\\end{abstract})"
        "6.正文≤20页(从第3页起算)"
        "7.页码\\setcounter{page}{1}放在摘要前"
        "8.封面用\\includepdf插入"
        "9.图表编号：图1/表1分别编号"
        "10.公式重要者右对齐编号"
        "逐条对照检查，只列违规项（附行号）。全部合规回复'格式合规，无问题'。直接输出。"
    ),
    "citation-audit": (
        "你是参考文献核验员。逐条验证文献真实性和引用正确性。"
        "输出：[OK/FAIL] 文献N → 结果。直接输出。"
    ),
    "result-to-claim": (
        "你是数据分析员。从数值结果提取论文声明。"
        "每条格式：[声明] xxx（支撑数据：yyy）。输出3-5条。直接输出。"
    ),
}


def call_gemini(prompt: str, model: str = "gemini-2.5-flash", task: str = "") -> str:
    """调用 Gemini API。如果有 API Key 则通过 HTTP 接口调用；否则通过本地 gemini CLI 运行。"""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    system_instruction = SYSTEM_PROMPTS.get(task, "") if task else ""
    
    if gemini_key:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.4 if "pro" in model else 0.2,
        }
        
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {gemini_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # 回退到本地 gemini CLI 运行
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"System instruction:\n{system_instruction}\n\nUser Prompt:\n{prompt}"
        
    try:
        import subprocess
        res = subprocess.run(
            ["gemini", "--skip-trust", "-p", full_prompt],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=sys.platform.startswith("win")
        )
        if res.returncode == 0:
            out = res.stdout
            lines = out.split("\n")
            cleaned_lines = []
            for l in lines:
                if "Warning: 256-color" in l or "Ripgrep is not" in l:
                    continue
                cleaned_lines.append(l)
            return "\n".join(cleaned_lines).strip()
        else:
            raise RuntimeError(f"Gemini CLI error: {res.stderr}")
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}")


def call_mimo(prompt: str, model: str = "mimo-v2.5",
              max_tokens: int = 16384, task: str = "") -> str:
    if model.startswith("gemini"):
        return call_gemini(prompt, model, task=task)
        
    if not MIMO_API_KEY:
        raise RuntimeError("MIMO_API_KEY not set")

    messages = []
    if task and task in SYSTEM_PROMPTS:
        messages.append({"role": "system", "content": SYSTEM_PROMPTS[task]})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.5 if "pro" in model else 0.3,
    }

    url = f"{MIMO_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MIMO_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            return _extract_response(msg)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"MiMo {e.code}: {e.read().decode('utf-8')[:300]}")
    except Exception as e:
        raise RuntimeError(f"MiMo error: {e}")


TASK_MODEL = {
    "research-lit": "mimo-v2.5",
    "exa-search": "mimo-v2.5",
    "arxiv": "mimo-v2.5",
    "semantic-scholar": "mimo-v2.5",
    "comm-lit-review": "mimo-v2.5",
    "run-experiment": "mimo-v2.5",
    "analyze-results": "mimo-v2.5",
    "paper-reference": "mimo-v2.5",
    "contest-format": "mimo-v2.5",
    "citation-audit": "mimo-v2.5",
    "novelty-check": "mimo-v2.5-pro",
    "result-to-claim": "mimo-v2.5-pro",
    "figure-spec": "gemini-2.5-flash",
    "mermaid-diagram": "gemini-2.5-flash",
    "paper-claim-audit": "gemini-2.5-pro",
    "auto-review-loop": "gemini-2.5-pro",
    "auto-paper-improvement-loop": "gemini-2.5-pro",
}


def get_model(task: str) -> str:
    return TASK_MODEL.get(task, "mimo-v2.5")
